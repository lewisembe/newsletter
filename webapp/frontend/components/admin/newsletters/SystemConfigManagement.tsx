"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { Loader2, Save, Settings } from "lucide-react";

interface SystemConfig {
  key: string;
  value: string;
  description: string | null;
}

export default function SystemConfigManagement() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [executionMode, setExecutionMode] = useState<"sequential" | "parallel">(
    "sequential"
  );
  const [maxParallel, setMaxParallel] = useState(3);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get("/system-config");
      // Handle both array response and object with configs property
      const configs = Array.isArray(response.data)
        ? response.data
        : (response.data?.configs || []);

      // Parse execution mode
      const modeConfig = configs.find(
        (c: SystemConfig) => c.key === "execution_mode"
      );
      if (modeConfig) {
        setExecutionMode(modeConfig.value as "sequential" | "parallel");
      }

      // Parse max parallel
      const maxConfig = configs.find(
        (c: SystemConfig) => c.key === "max_parallel_executions"
      );
      if (maxConfig) {
        setMaxParallel(parseInt(maxConfig.value));
      }
    } catch (err) {
      console.error("Error loading config:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      // Update execution mode
      await apiClient.put("/system-config/execution_mode", {
        value: executionMode,
      });

      // Update max parallel
      await apiClient.put("/system-config/max_parallel_executions", {
        value: maxParallel.toString(),
      });

      alert("✅ Configuración guardada correctamente");
    } catch (err: any) {
      alert(err.response?.data?.detail || "Error al guardar configuración");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-blue-600" size={48} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">
          Configuración del Sistema
        </h2>
        <p className="text-sm text-gray-600 mt-1">
          Modo de ejecución de tareas programadas
        </p>
      </div>

      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        {/* Execution Mode */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Modo de Ejecución
          </label>

          <div className="space-y-2">
            <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input
                type="radio"
                name="executionMode"
                checked={executionMode === "sequential"}
                onChange={() => setExecutionMode("sequential")}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <div className="flex-1">
                <div className="font-medium text-sm text-gray-900">
                  Secuencial (Recomendado)
                </div>
                <div className="text-xs text-gray-600">
                  Tareas una a la vez, sin conflictos
                </div>
              </div>
            </label>

            <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input
                type="radio"
                name="executionMode"
                checked={executionMode === "parallel"}
                onChange={() => setExecutionMode("parallel")}
                className="w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <div className="flex-1">
                <div className="font-medium text-sm text-gray-900">
                  Paralelo (Avanzado)
                </div>
                <div className="text-xs text-gray-600">
                  Múltiples tareas simultáneas
                </div>
              </div>
            </label>
          </div>
        </div>

        {/* Max Parallel (only shown if parallel mode) */}
        {executionMode === "parallel" && (
          <div className="animate-in fade-in duration-300">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Máximo de Ejecuciones Paralelas
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={1}
                max={10}
                value={maxParallel}
                onChange={(e) => setMaxParallel(parseInt(e.target.value))}
                className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex items-center justify-center w-12 h-10 bg-blue-100 text-blue-700 font-bold rounded-lg">
                {maxParallel}
              </div>
            </div>
          </div>
        )}

        {/* Save Button */}
        <div className="flex items-center justify-end pt-4 border-t">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {saving ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Guardando...
              </>
            ) : (
              <>
                <Save size={18} />
                Guardar
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
