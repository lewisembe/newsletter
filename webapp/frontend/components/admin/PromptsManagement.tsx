"use client";

import { useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { CheckCircle2, Loader2, Pencil, Play, RefreshCw, XCircle } from "lucide-react";

type PromptStatus = "draft" | "approved" | "archived";

interface Prompt {
  id: string;
  name: string;
  stage: string;
  operation: string;
  scope: string;
  system_prompt: string;
  user_prompt_template: string;
  placeholders: string[];
  response_format: any;
  default_model: string | null;
  temperature: number | null;
  max_tokens: number | null;
  batch_size: number | null;
  version: number;
  status: PromptStatus;
  notes?: string;
  updated_at?: string;
}

const stageOptions = ["01", "02", "03", "04", "05", "general"];

export default function PromptsManagement() {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [testingPrompt, setTestingPrompt] = useState<Prompt | null>(null);
  const [formData, setFormData] = useState<Partial<Prompt>>({});
  const [testPayload, setTestPayload] = useState<string>("{}");
  const [testResult, setTestResult] = useState<any>(null);
  const [testLoading, setTestLoading] = useState<boolean>(false);

  useEffect(() => {
    loadPrompts();
  }, []);

  const loadPrompts = async () => {
    try {
      setLoading(true);
      setError(null);
      const resp = await apiClient.get("/prompts");
      setPrompts(resp.data.prompts || []);
    } catch (err: any) {
      console.error("Error loading prompts", err);
      setError(err.response?.data?.detail || "No se pudieron cargar los prompts");
    } finally {
      setLoading(false);
    }
  };

  const filteredPrompts = useMemo(() => {
    return prompts.filter((p) => {
      const matchesStage = activeStage === "all" || p.stage === activeStage;
      const term = search.trim().toLowerCase();
      const matchesSearch =
        !term ||
        p.name.toLowerCase().includes(term) ||
        p.operation.toLowerCase().includes(term) ||
        p.stage.toLowerCase().includes(term) ||
        (p.notes || "").toLowerCase().includes(term);
      return matchesStage && matchesSearch;
    });
  }, [prompts, activeStage, search]);

  const handleEdit = (prompt: Prompt) => {
    setEditingPrompt(prompt);
    setFormData(prompt);
  };

  const handleSave = async () => {
    if (!editingPrompt) return;
    try {
      const payload = {
        ...formData,
        placeholders: formData.placeholders || [],
      };
      await apiClient.put(`/prompts/${editingPrompt.id}`, payload);
      await loadPrompts();
      setEditingPrompt(null);
      setFormData({});
    } catch (err: any) {
      alert(err.response?.data?.detail || "No se pudo guardar el prompt");
    }
  };

  const handleTest = async () => {
    if (!testingPrompt) return;
    try {
      setTestLoading(true);
      setTestResult(null);
      const payload = JSON.parse(testPayload || "{}");
      const resp = await apiClient.post(`/prompts/${testingPrompt.id}/test`, payload);
      setTestResult(resp.data);
    } catch (err: any) {
      console.error("Test error", err);
      setTestResult({ error: err.response?.data?.detail || "Error al probar el prompt" });
    } finally {
      setTestLoading(false);
    }
  };

  const statusBadge = (status: PromptStatus) => {
    switch (status) {
      case "approved":
        return <span className="inline-flex items-center text-xs text-green-700 bg-green-100 px-2 py-1 rounded">Aprobado</span>;
      case "draft":
        return <span className="inline-flex items-center text-xs text-yellow-700 bg-yellow-100 px-2 py-1 rounded">Borrador</span>;
      default:
        return <span className="inline-flex items-center text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">Archivado</span>;
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-32">
        <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded">
        <div className="font-semibold mb-1">Error</div>
        <div>{error}</div>
        <button onClick={loadPrompts} className="mt-2 inline-flex items-center text-sm text-red-700 hover:underline">
          <RefreshCw className="w-4 h-4 mr-1" /> Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Prompts</h2>
          <p className="text-sm text-gray-600">Gestiona prompts, modelos y pruebas desde un solo lugar.</p>
        </div>
        <div className="flex gap-3 items-center">
          <select
            className="border rounded px-3 py-2 text-sm"
            value={activeStage}
            onChange={(e) => setActiveStage(e.target.value)}
          >
            <option value="all">Todos los stages</option>
            {stageOptions.map((opt) => (
              <option key={opt} value={opt}>
                Stage {opt}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Buscar por nombre u operación"
            className="border rounded px-3 py-2 text-sm w-56"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            onClick={loadPrompts}
            className="inline-flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-800 text-sm font-medium px-3 py-2 rounded"
          >
            <RefreshCw className="w-4 h-4" /> Refrescar
          </button>
        </div>
      </div>

      <div className="overflow-x-auto border border-gray-200 rounded-md">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Stage</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Operación</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Modelo</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Temp</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Max tokens</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Batch</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Estado</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Versión</th>
              <th className="px-4 py-2 text-left font-semibold text-gray-700">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filteredPrompts.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-xs text-gray-700">{p.stage}</td>
                <td className="px-4 py-2">
                  <div className="text-gray-900 font-medium">{p.operation}</div>
                  <div className="text-xs text-gray-500">{p.name}</div>
                </td>
                <td className="px-4 py-2 text-gray-800">{p.default_model || "—"}</td>
                <td className="px-4 py-2 text-gray-800">{p.temperature ?? "—"}</td>
                <td className="px-4 py-2 text-gray-800">{p.max_tokens ?? "—"}</td>
                <td className="px-4 py-2 text-gray-800">{p.batch_size ?? "—"}</td>
                <td className="px-4 py-2">{statusBadge(p.status)}</td>
                <td className="px-4 py-2 text-gray-800">{p.version}</td>
                <td className="px-4 py-2 space-x-2">
                  <button
                    onClick={() => handleEdit(p)}
                    className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 text-sm"
                  >
                    <Pencil className="w-4 h-4" /> Editar
                  </button>
                  <button
                    onClick={() => {
                      setTestingPrompt(p);
                      setTestPayload("{}");
                      setTestResult(null);
                    }}
                    className="inline-flex items-center gap-1 text-emerald-600 hover:text-emerald-800 text-sm"
                  >
                    <Play className="w-4 h-4" /> Probar
                  </button>
                </td>
              </tr>
            ))}
            {filteredPrompts.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-6 text-center text-gray-500">
                  No hay prompts para mostrar.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Edit modal */}
      {editingPrompt && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-md shadow-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Editar prompt</h3>
                <p className="text-sm text-gray-600">
                  {editingPrompt.stage} · {editingPrompt.operation} · v{editingPrompt.version}
                </p>
              </div>
              <button onClick={() => setEditingPrompt(null)} className="text-gray-500 hover:text-gray-700">
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Modelo por defecto</label>
                <input
                  className="w-full border rounded px-3 py-2 text-sm"
                  value={formData.default_model || ""}
                  onChange={(e) => setFormData({ ...formData, default_model: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-sm font-medium text-gray-700">Temp</label>
                  <input
                    className="w-full border rounded px-3 py-2 text-sm"
                    type="number"
                    step="0.01"
                    value={formData.temperature ?? ""}
                    onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Max tokens</label>
                  <input
                    className="w-full border rounded px-3 py-2 text-sm"
                    type="number"
                    value={formData.max_tokens ?? ""}
                    onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) || null })}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Batch size</label>
                  <input
                    className="w-full border rounded px-3 py-2 text-sm"
                    type="number"
                    value={formData.batch_size ?? ""}
                    onChange={(e) => setFormData({ ...formData, batch_size: parseInt(e.target.value) || null })}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Placeholders (coma separados)</label>
              <input
                className="w-full border rounded px-3 py-2 text-sm"
                value={(formData.placeholders || []).join(",")}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    placeholders: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">System prompt</label>
              <textarea
                className="w-full border rounded px-3 py-2 text-sm h-32"
                value={formData.system_prompt || ""}
                onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">User prompt template</label>
              <textarea
                className="w-full border rounded px-3 py-2 text-sm h-40"
                value={formData.user_prompt_template || ""}
                onChange={(e) => setFormData({ ...formData, user_prompt_template: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Response format (JSON)</label>
              <textarea
                className="w-full border rounded px-3 py-2 text-sm h-28 font-mono"
                value={
                  formData.response_format
                    ? JSON.stringify(formData.response_format, null, 2)
                    : JSON.stringify({}, null, 2)
                }
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value || "{}");
                    setFormData({ ...formData, response_format: parsed });
                    setError(null);
                  } catch (err) {
                    setError("Response format no es JSON válido");
                  }
                }}
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setEditingPrompt(null)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
              >
                Cancelar
              </button>
              <button
                onClick={handleSave}
                className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded text-sm"
              >
                <CheckCircle2 className="w-4 h-4" /> Guardar cambios
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Test modal */}
      {testingPrompt && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-md shadow-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Probar prompt</h3>
                <p className="text-sm text-gray-600">
                  {testingPrompt.stage} · {testingPrompt.operation} · {testingPrompt.name}
                </p>
              </div>
              <button onClick={() => setTestingPrompt(null)} className="text-gray-500 hover:text-gray-700">
                ✕
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Payload de prueba (JSON)</label>
              <textarea
                className="w-full border rounded px-3 py-2 text-sm h-40 font-mono"
                value={testPayload}
                onChange={(e) => setTestPayload(e.target.value)}
              />
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleTest}
                disabled={testLoading}
                className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded text-sm disabled:opacity-60"
              >
                {testLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                Ejecutar
              </button>
            </div>

            {testResult && (
              <div className="border rounded bg-gray-50 p-3 space-y-2">
                <div className="font-semibold text-sm text-gray-800 flex items-center gap-2">
                  {testResult.error ? (
                    <>
                      <XCircle className="w-4 h-4 text-red-500" /> Error
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" /> Resultado
                    </>
                  )}
                </div>
                <pre className="text-xs bg-white border rounded p-3 overflow-x-auto">
{JSON.stringify(testResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
