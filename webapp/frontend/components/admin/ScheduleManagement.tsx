"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api-client";

interface Schedule {
  id: number;
  name: string;
  cron_expression: string;
  api_key_id: number;
  source_filter: string[] | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  next_run_at: string | null;
}

interface APIKey {
  id: number;
  alias: string;
}

interface Source {
  id: number;
  name: string;
  base_url: string;
  is_active: boolean;
}

interface ScheduleManagementProps {
  refreshTrigger?: number;
}

export default function ScheduleManagement({ refreshTrigger }: ScheduleManagementProps) {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [hasRunningExecution, setHasRunningExecution] = useState(false);

  // Edit form state (using intuitive interface like creation)
  const [formName, setFormName] = useState("");
  const [formFrequency, setFormFrequency] = useState<"daily" | "weekly" | "hourly">("daily");
  const [formHour, setFormHour] = useState("06");
  const [formMinute, setFormMinute] = useState("00");
  const [formDayOfWeek, setFormDayOfWeek] = useState<number>(1);
  const [formApiKey, setFormApiKey] = useState<number | null>(null);
  const [formSources, setFormSources] = useState<string[]>([]);

  // Parse CRON to human-readable format (for display in table)
  const parseCronToHumanReadable = (cronExpression: string): { frequency: string; time: string } => {
    const parts = cronExpression.split(' ');
    if (parts.length !== 5) {
      return { frequency: 'Desconocido', time: cronExpression };
    }

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    // Convert UTC time to local time
    const utcHour = parseInt(hour);
    const utcMinute = parseInt(minute);

    // Create a date object to handle timezone conversion
    const now = new Date();
    const utcDate = new Date(Date.UTC(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      isNaN(utcHour) ? 0 : utcHour,
      isNaN(utcMinute) ? 0 : utcMinute,
      0
    ));

    const localHour = utcDate.getHours();
    const localMinute = utcDate.getMinutes();
    const timeStr = `${localHour.toString().padStart(2, '0')}:${localMinute.toString().padStart(2, '0')}`;

    // Determine frequency
    if (hour === '*' && dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
      return { frequency: '⏱️ Cada hora', time: `minuto ${minute}` };
    } else if (dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
      return { frequency: '📅 Diaria', time: timeStr };
    } else if (dayOfMonth === '*' && month === '*' && dayOfWeek !== '*') {
      const days = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
      const dayIndex = parseInt(dayOfWeek);
      return { frequency: `📆 Semanal (${days[dayIndex] || dayOfWeek})`, time: timeStr };
    } else if (dayOfMonth !== '*') {
      return { frequency: `📆 Mensual (día ${dayOfMonth})`, time: timeStr };
    }

    return { frequency: 'Personalizado', time: cronExpression };
  };

  // Parse CRON back to form values for editing
  const parseCronToFormValues = (cronExpression: string): {
    frequency: "daily" | "weekly" | "hourly";
    hour: string;
    minute: string;
    dayOfWeek: number;
  } => {
    const parts = cronExpression.split(' ');
    if (parts.length !== 5) {
      return { frequency: 'daily', hour: '06', minute: '00', dayOfWeek: 1 };
    }

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    // Determine frequency
    let frequency: "daily" | "weekly" | "hourly" = "daily";
    if (hour === '*') {
      frequency = 'hourly';
    } else if (dayOfWeek !== '*') {
      frequency = 'weekly';
    } else {
      frequency = 'daily';
    }

    // Convert UTC time back to local time
    const utcHour = parseInt(hour);
    const utcMinute = parseInt(minute);

    let localHour = '06';
    let localMinute = '00';

    if (!isNaN(utcHour) && !isNaN(utcMinute)) {
      const now = new Date();
      const utcDate = new Date(Date.UTC(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        utcHour,
        utcMinute,
        0
      ));
      localHour = utcDate.getHours().toString().padStart(2, '0');
      localMinute = utcDate.getMinutes().toString().padStart(2, '0');
    } else {
      // For hourly, just use the minute
      localMinute = minute.padStart(2, '0');
    }

    const parsedDayOfWeek = dayOfWeek !== '*' ? parseInt(dayOfWeek) : 1;

    return {
      frequency,
      hour: localHour,
      minute: localMinute,
      dayOfWeek: parsedDayOfWeek
    };
  };

  // Convert local time to UTC CRON expression
  const convertToUTCCron = (
    frequency: "daily" | "weekly" | "hourly",
    localHour: string,
    localMinute: string,
    dayOfWeek?: number
  ): string => {
    if (frequency === "hourly") {
      return `${localMinute} * * * *`;
    }

    const now = new Date();
    const localDate = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      parseInt(localHour),
      parseInt(localMinute),
      0
    );

    const utcHour = localDate.getUTCHours();
    const utcMinute = localDate.getUTCMinutes();

    if (frequency === "daily") {
      return `${utcMinute} ${utcHour} * * *`;
    }

    if (frequency === "weekly" && dayOfWeek !== undefined) {
      return `${utcMinute} ${utcHour} * * ${dayOfWeek}`;
    }

    return `${utcMinute} ${utcHour} * * *`;
  };

  // Fetch schedules (filter only scraping executions)
  const fetchSchedules = useCallback(async () => {
    try {
      const response = await apiClient.get("/stage-executions/schedules", {
        params: { execution_type: '01_extract_urls' }
      });
      const schedulesData = Array.isArray(response.data) ? response.data : [];
      setSchedules(schedulesData);
    } catch (err: any) {
      console.error("Failed to fetch schedules:", err);
      setSchedules([]); // Ensure it's always an array even on error
    }
  }, []);

  // Fetch API keys
  const fetchApiKeys = useCallback(async () => {
    try {
      const response = await apiClient.get("/api-keys");
      // Backend returns { total, api_keys }, extract the api_keys array
      const keys = response.data?.api_keys || [];
      setApiKeys(Array.isArray(keys) ? keys : []);
      if (keys.length > 0 && !formApiKey) {
        setFormApiKey(keys[0].id);
      }
    } catch (err: any) {
      console.error("Failed to fetch API keys:", err);
      setApiKeys([]); // Ensure it's always an array even on error
    }
  }, [formApiKey]);

  // Fetch sources
  const fetchSources = useCallback(async () => {
    try {
      const response = await apiClient.get("/sources");
      const sourcesData = Array.isArray(response.data) ? response.data : [];
      setSources(sourcesData.filter((s: Source) => s.is_active));
    } catch (err: any) {
      console.error("Failed to fetch sources:", err);
      setSources([]); // Ensure it's always an array even on error
    }
  }, []);

  // Check if there's any running execution
  const checkRunningExecution = useCallback(async () => {
    try {
      const response = await apiClient.get("/stage-executions/running/check");
      setHasRunningExecution(response.data?.has_running || false);
    } catch (err: any) {
      console.error("Failed to check running execution:", err);
      setHasRunningExecution(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchSchedules();
    fetchApiKeys();
    fetchSources();
    checkRunningExecution();
  }, [fetchSchedules, fetchApiKeys, fetchSources, checkRunningExecution]);

  // Refresh when trigger changes
  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      fetchSchedules();
      checkRunningExecution();
    }
  }, [refreshTrigger, fetchSchedules, checkRunningExecution]);

  // Poll for running execution status every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      checkRunningExecution();
    }, 5000);

    return () => clearInterval(interval);
  }, [checkRunningExecution]);

  // Handle update schedule
  const handleUpdate = async () => {
    if (!formName || !formApiKey || !editingId) {
      setError("Por favor completa todos los campos requeridos");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Convert to CRON based on frequency
      const cronExpression = convertToUTCCron(
        formFrequency,
        formHour,
        formMinute,
        formDayOfWeek
      );

      const payload = {
        name: formName,
        cron_expression: cronExpression,
        api_key_id: formApiKey,
        source_filter: formSources.length > 0 ? formSources : null,
        is_active: true,
      };

      await apiClient.put(`/stage-executions/schedules/${editingId}`, payload);
      setSuccess("¡Programación actualizada exitosamente!");

      // Reset form
      setFormName("");
      setFormFrequency("daily");
      setFormHour("06");
      setFormMinute("00");
      setFormDayOfWeek(1);
      setFormSources([]);
      setShowEditModal(false);
      setEditingId(null);

      // Refresh list
      await fetchSchedules();
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Error al actualizar la programación"
      );
    } finally {
      setLoading(false);
    }
  };

  // Handle edit schedule
  const handleEdit = (schedule: Schedule) => {
    setEditingId(schedule.id);
    setFormName(schedule.name);
    setFormApiKey(schedule.api_key_id);
    setFormSources(schedule.source_filter || []);

    // Parse CRON back to form values
    const { frequency, hour, minute, dayOfWeek } = parseCronToFormValues(schedule.cron_expression);
    setFormFrequency(frequency);
    setFormHour(hour);
    setFormMinute(minute);
    setFormDayOfWeek(dayOfWeek);

    setShowEditModal(true);
    setError(null);
    setSuccess(null);
  };

  // Handle toggle active
  const handleToggle = async (id: number) => {
    try {
      await apiClient.put(`/stage-executions/schedules/${id}/toggle`);
      setSuccess("Estado de programación actualizado");
      await fetchSchedules();
    } catch (err: any) {
      setError("Error al cambiar el estado de la programación");
    }
  };

  // Handle delete
  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Estás seguro de que deseas eliminar la programación "${name}"?`)) {
      return;
    }

    try {
      await apiClient.delete(`/stage-executions/schedules/${id}`);
      setSuccess("Programación eliminada exitosamente");
      await fetchSchedules();
    } catch (err: any) {
      setError("Error al eliminar la programación");
    }
  };

  // Handle execute now
  const handleExecuteNow = async (schedule: Schedule) => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Extract source names from schedule if available
      const sourceNames = schedule.source_filter || null;

      const payload = {
        api_key_id: schedule.api_key_id,
        source_names: sourceNames,
      };

      await apiClient.post("/stage-executions", payload);
      setSuccess(`Ejecución de "${schedule.name}" iniciada exitosamente`);

      // Immediately check for running execution to disable button
      await checkRunningExecution();
    } catch (err: any) {
      setError(
        err.response?.data?.detail || `Error al ejecutar "${schedule.name}"`
      );
    } finally {
      setLoading(false);
    }
  };

  // Handle source toggle
  const toggleSource = (sourceName: string) => {
    setFormSources((prev) =>
      prev.includes(sourceName)
        ? prev.filter((s) => s !== sourceName)
        : [...prev, sourceName]
    );
  };

  return (
    <div className="space-y-6">
      {/* Alert Messages */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded">
          {success}
        </div>
      )}

      {/* Edit Schedule Modal */}
      {showEditModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 sticky top-0 bg-white">
              <div className="flex justify-between items-center">
                <h3 className="text-xl font-semibold">Editar Programación</h3>
                <button
                  onClick={() => {
                    setShowEditModal(false);
                    setEditingId(null);
                    setError(null);
                  }}
                  className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
                  disabled={loading}
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nombre de Programación *
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="ej., Extracción Diaria Matutina"
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                  disabled={loading}
                />
              </div>

              {/* Frequency Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Frecuencia *
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setFormFrequency("hourly")}
                    className={`p-3 border-2 rounded-lg transition-all ${
                      formFrequency === "hourly"
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                    disabled={loading}
                  >
                    <div className="text-2xl mb-1">⏱️</div>
                    <div className="text-sm font-medium">Cada Hora</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormFrequency("daily")}
                    className={`p-3 border-2 rounded-lg transition-all ${
                      formFrequency === "daily"
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                    disabled={loading}
                  >
                    <div className="text-2xl mb-1">📅</div>
                    <div className="text-sm font-medium">Diaria</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormFrequency("weekly")}
                    className={`p-3 border-2 rounded-lg transition-all ${
                      formFrequency === "weekly"
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                    disabled={loading}
                  >
                    <div className="text-2xl mb-1">📆</div>
                    <div className="text-sm font-medium">Semanal</div>
                  </button>
                </div>
              </div>

              {/* Day of Week Selector (only for weekly) */}
              {formFrequency === "weekly" && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Día de la Semana *
                  </label>
                  <select
                    value={formDayOfWeek}
                    onChange={(e) => setFormDayOfWeek(Number(e.target.value))}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                    disabled={loading}
                  >
                    <option value={1}>Lunes</option>
                    <option value={2}>Martes</option>
                    <option value={3}>Miércoles</option>
                    <option value={4}>Jueves</option>
                    <option value={5}>Viernes</option>
                    <option value={6}>Sábado</option>
                    <option value={0}>Domingo</option>
                  </select>
                </div>
              )}

              {/* Time Selector */}
              {formFrequency !== "hourly" ? (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Hora de Ejecución *
                  </label>
                  <div className="flex space-x-3 items-center">
                    <select
                      value={formHour}
                      onChange={(e) => setFormHour(e.target.value)}
                      className="flex-1 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
                      disabled={loading}
                    >
                      {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
                        <option key={hour} value={hour.toString().padStart(2, '0')}>
                          {hour.toString().padStart(2, '0')}
                        </option>
                      ))}
                    </select>
                    <span className="text-2xl text-gray-400">:</span>
                    <select
                      value={formMinute}
                      onChange={(e) => setFormMinute(e.target.value)}
                      className="flex-1 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
                      disabled={loading}
                    >
                      {Array.from({ length: 60 }, (_, i) => i).map((minute) => (
                        <option key={minute} value={minute.toString().padStart(2, '0')}>
                          {minute.toString().padStart(2, '0')}
                        </option>
                      ))}
                    </select>
                  </div>
                  <p className="text-xs text-gray-500 mt-1 text-center">
                    🕐 Tu hora local
                  </p>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Minuto de Ejecución *
                  </label>
                  <select
                    value={formMinute}
                    onChange={(e) => setFormMinute(e.target.value)}
                    className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
                    disabled={loading}
                  >
                    {Array.from({ length: 60 }, (_, i) => i).map((minute) => (
                      <option key={minute} value={minute.toString().padStart(2, '0')}>
                        {minute.toString().padStart(2, '0')}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1 text-center">
                    Se ejecutará cada hora en el minuto {formMinute}
                  </p>
                </div>
              )}

              {/* API Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Clave API *
                </label>
                <select
                  value={formApiKey || ""}
                  onChange={(e) => setFormApiKey(Number(e.target.value))}
                  className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
                  disabled={loading}
                >
                  {apiKeys.map((key) => (
                    <option key={key.id} value={key.id}>
                      {key.alias}
                    </option>
                  ))}
                </select>
              </div>

              {/* Sources */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Fuentes (opcional)
                </label>
                <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-3 border border-gray-300 rounded">
                  {sources.map((source) => (
                    <label
                      key={source.id}
                      className="flex items-center space-x-2 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={formSources.includes(source.name)}
                        onChange={() => toggleSource(source.name)}
                        disabled={loading}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700">{source.name}</span>
                    </label>
                  ))}
                </div>
                {formSources.length > 0 && (
                  <p className="text-sm text-gray-500 mt-2">
                    Seleccionadas: {formSources.length} fuente(s)
                  </p>
                )}
              </div>
            </div>

            {/* Modal Footer with Buttons */}
            <div className="p-6 border-t border-gray-200 bg-gray-50 sticky bottom-0 flex gap-3">
              <button
                onClick={handleUpdate}
                disabled={loading || !formName || !formApiKey}
                className="flex-1 bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                {loading ? "Actualizando..." : "✨ Actualizar Programación"}
              </button>
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setEditingId(null);
                  setFormName("");
                  setFormFrequency("daily");
                  setFormHour("06");
                  setFormMinute("00");
                  setFormDayOfWeek(1);
                  setFormSources([]);
                  setError(null);
                }}
                className="px-6 py-2 border border-gray-300 rounded hover:bg-gray-100"
                disabled={loading}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Schedules Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-6 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Ejecuciones Programadas</h3>
            <button
              onClick={fetchSchedules}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              Refrescar
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Nombre
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Periodicidad
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hora
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Fuentes
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Última Ejecución
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {schedules.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-gray-500">
                    No se encontraron programaciones
                  </td>
                </tr>
              ) : (
                schedules.map((schedule) => {
                  const { frequency, time } = parseCronToHumanReadable(schedule.cron_expression);
                  return (
                  <tr key={schedule.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {schedule.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {frequency}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 font-medium">
                      {time}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {schedule.source_filter && schedule.source_filter.length > 0
                        ? schedule.source_filter.join(", ")
                        : "Todas las fuentes"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded-full ${
                          schedule.is_active
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {schedule.is_active ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {schedule.last_run_at
                        ? new Date(schedule.last_run_at).toLocaleString('es-ES')
                        : "Nunca"}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                      <button
                        onClick={() => handleExecuteNow(schedule)}
                        className={`font-medium ${
                          hasRunningExecution
                            ? "text-gray-400 cursor-not-allowed"
                            : "text-green-600 hover:text-green-700"
                        }`}
                        disabled={loading || hasRunningExecution}
                        title={
                          hasRunningExecution
                            ? "Ya hay una ejecución en progreso. Por favor espera a que termine."
                            : "Ejecutar ahora esta programación"
                        }
                      >
                        ▶️ Ejecutar
                      </button>
                      <button
                        onClick={() => handleEdit(schedule)}
                        className="text-indigo-600 hover:text-indigo-700"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleToggle(schedule.id)}
                        className="text-blue-600 hover:text-blue-700"
                      >
                        {schedule.is_active ? "Desactivar" : "Activar"}
                      </button>
                      <button
                        onClick={() => handleDelete(schedule.id, schedule.name)}
                        className="text-red-600 hover:text-red-700"
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
