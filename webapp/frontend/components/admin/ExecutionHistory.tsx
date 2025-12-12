"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api-client";
import ExecutionDetailModal from "./ExecutionDetailModal";
import { Eye } from "lucide-react";

// Format seconds to hh:mm:ss
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Clock component
function Clock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex items-center space-x-2 text-gray-600">
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span className="text-sm font-medium">
        {time.toLocaleTimeString('es-ES')}
      </span>
      <span className="text-xs text-gray-400">
        {time.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' })}
      </span>
    </div>
  );
}

interface ExecutionHistory {
  id: number;
  schedule_id: number | null;
  schedule_name: string | null;
  execution_type: string;
  stage_name: string;
  status: string;
  api_key_id: number | null;
  api_key_alias: string | null;
  api_keys_used: number[] | null;  // Array of API key IDs used (primary + fallbacks)
  parameters: any | null;
  celery_task_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_items: number;
  processed_items: number;
  updated_items: number;
  failed_items: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  cost_eur: number;
  error_message: string | null;
  log_file: string | null;
  duration_seconds: number | null;
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

interface ExecutionHistoryProps {
  onScheduleCreated?: () => void;
}

export default function ExecutionHistory({ onScheduleCreated }: ExecutionHistoryProps) {
  const [executions, setExecutions] = useState<ExecutionHistory[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Helper: Get API key alias by ID
  const getApiKeyAlias = (keyId: number): string => {
    const key = apiKeys.find(k => k.id === keyId);
    return key ? key.alias : `ID ${keyId}`;
  };

  // Tab state
  const [activeTab, setActiveTab] = useState<'manual' | 'scheduled'>('manual');

  // Detail modal state
  const [selectedExecutionId, setSelectedExecutionId] = useState<number | null>(null);

  // Manual execution form state
  const [selectedApiKey, setSelectedApiKey] = useState<number | null>(null);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [useFallback, setUseFallback] = useState<boolean>(true);  // Enable fallback by default

  // Schedule creation form state
  const [scheduleName, setScheduleName] = useState("");
  const [scheduleApiKey, setScheduleApiKey] = useState<number | null>(null);
  const [scheduleSources, setScheduleSources] = useState<string[]>([]);
  const [scheduleFrequency, setScheduleFrequency] = useState<"daily" | "weekly" | "hourly">("daily");
  const [scheduleHour, setScheduleHour] = useState("06");
  const [scheduleMinute, setScheduleMinute] = useState("00");
  const [scheduleDayOfWeek, setScheduleDayOfWeek] = useState<number>(1); // 1 = Monday

  // Polling state
  const [pollingExecutions, setPollingExecutions] = useState<Set<number>>(
    new Set()
  );

  // Fetch executions
  const fetchExecutions = useCallback(async () => {
    try {
      const response = await apiClient.get("/stage-executions", {
        params: { limit: 50 },
      });
      setExecutions(response.data);

      // Update polling set for running or pending executions
      const running = response.data
        .filter((ex: ExecutionHistory) => ex.status === "running" || ex.status === "pending")
        .map((ex: ExecutionHistory) => ex.id);
      setPollingExecutions(new Set(running));
    } catch (err: any) {
      console.error("Failed to fetch executions:", err);
    }
  }, []);

  // Fetch API keys
  const fetchApiKeys = useCallback(async () => {
    try {
      const response = await apiClient.get("/api-keys");
      const keys = response.data.api_keys || response.data;
      setApiKeys(keys);
      if (keys.length > 0) {
        if (!selectedApiKey) {
          setSelectedApiKey(keys[0].id);
        }
        if (!scheduleApiKey) {
          setScheduleApiKey(keys[0].id);
        }
      }
    } catch (err: any) {
      console.error("Failed to fetch API keys:", err);
    }
  }, [selectedApiKey, scheduleApiKey]);

  // Fetch sources
  const fetchSources = useCallback(async () => {
    try {
      const response = await apiClient.get("/sources");
      setSources(response.data.filter((s: Source) => s.is_active));
    } catch (err: any) {
      console.error("Failed to fetch sources:", err);
    }
  }, []);

  // Poll status for running executions
  useEffect(() => {
    if (pollingExecutions.size === 0) return;

    const interval = setInterval(async () => {
      for (const id of pollingExecutions) {
        try {
          const response = await apiClient.get(
            `/stage-executions/${id}/status`
          );
          const execution = response.data;

          // Update execution in list
          setExecutions((prev) =>
            prev.map((ex) => (ex.id === id ? execution : ex))
          );

          // Remove from polling if completed/failed
          if (
            execution.status === "completed" ||
            execution.status === "failed"
          ) {
            setPollingExecutions((prev) => {
              const next = new Set(prev);
              next.delete(id);
              return next;
            });
          }
        } catch (err) {
          console.error(`Failed to poll execution ${id}:`, err);
        }
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [pollingExecutions]);

  // Initial load
  useEffect(() => {
    fetchExecutions();
    fetchApiKeys();
    fetchSources();
  }, [fetchExecutions, fetchApiKeys, fetchSources]);

  // Auto-refresh executions every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchExecutions();
    }, 10000); // 10 seconds

    return () => clearInterval(interval);
  }, [fetchExecutions]);

  // Check if there's any execution running
  const hasRunningExecution = executions.some(
    (ex) => ex.status === "running" || ex.status === "pending"
  );

  const handleAbort = async (executionId: number) => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      await apiClient.post(`/stage-executions/${executionId}/abort`);
      setSuccess(`Ejecución #${executionId} abortada`);
      await fetchExecutions();
    } catch (err: any) {
      setError(err.response?.data?.detail || "No se pudo abortar la ejecución");
    } finally {
      setLoading(false);
    }
  };

  // Handle manual execution
  const handleExecute = async () => {
    if (!selectedApiKey) {
      setError("Por favor selecciona una clave API");
      return;
    }

    if (hasRunningExecution) {
      setError("Ya hay una ejecución en curso. Por favor espera a que termine.");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        api_key_id: selectedApiKey,
        source_names: selectedSources.length > 0 ? selectedSources : null,
        use_fallback: useFallback,
      };

      const response = await apiClient.post("/stage-executions", payload);

      // Immediately add to executions list with pending status (optimistic update)
      const newExecution: ExecutionHistory = {
        ...response.data,
        status: 'pending'
      };
      setExecutions((prev) => [newExecution, ...prev]);

      setSuccess(
        `¡Ejecución iniciada exitosamente! ID: ${response.data.id}`
      );

      // Add to polling
      setPollingExecutions((prev) => new Set(prev).add(response.data.id));

      // Refresh list after a short delay to get updated data
      setTimeout(() => fetchExecutions(), 1000);

      // Reset form
      setSelectedSources([]);
    } catch (err: any) {
      // Handle 409 Conflict silently (execution already running)
      if (err.response?.status === 409) {
        setError("Ya hay una ejecución en curso. Por favor espera a que termine.");
      } else {
        setError(
          err.response?.data?.detail || "Error al iniciar la ejecución"
        );
      }
    } finally {
      setLoading(false);
    }
  };

  // Handle source toggle for manual execution
  const toggleSource = (sourceName: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceName)
        ? prev.filter((s) => s !== sourceName)
        : [...prev, sourceName]
    );
  };

  // Handle source toggle for schedule creation
  const toggleScheduleSource = (sourceName: string) => {
    setScheduleSources((prev) =>
      prev.includes(sourceName)
        ? prev.filter((s) => s !== sourceName)
        : [...prev, sourceName]
    );
  };

  // Convert local time to UTC CRON expression based on frequency
  const convertToUTCCron = (
    frequency: "daily" | "weekly" | "hourly",
    localHour: string,
    localMinute: string,
    dayOfWeek?: number
  ): string => {
    if (frequency === "hourly") {
      // Every hour at the specified minute
      return `${localMinute} * * * *`;
    }

    // Create a date object with today's date and the selected time
    const now = new Date();
    const localDate = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      parseInt(localHour),
      parseInt(localMinute),
      0
    );

    // Get UTC hour and minute
    const utcHour = localDate.getUTCHours();
    const utcMinute = localDate.getUTCMinutes();

    if (frequency === "daily") {
      // Every day at the specified time
      return `${utcMinute} ${utcHour} * * *`;
    }

    if (frequency === "weekly" && dayOfWeek !== undefined) {
      // Weekly on specific day at the specified time
      return `${utcMinute} ${utcHour} * * ${dayOfWeek}`;
    }

    // Default to daily
    return `${utcMinute} ${utcHour} * * *`;
  };

  // Handle create schedule
  const handleCreateSchedule = async () => {
    if (!scheduleName || !scheduleApiKey) {
      setError("Por favor completa todos los campos requeridos");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Convert to CRON based on frequency
      const cronExpression = convertToUTCCron(
        scheduleFrequency,
        scheduleHour,
        scheduleMinute,
        scheduleDayOfWeek
      );

      const payload = {
        name: scheduleName,
        cron_expression: cronExpression,
        api_key_id: scheduleApiKey,
        execution_target: '01_extract_urls',
        source_filter: scheduleSources.length > 0 ? scheduleSources : null,
        is_active: true,
      };

      await apiClient.post("/stage-executions/schedules", payload);

      // Generate success message based on frequency
      let successMsg = "¡Programación creada exitosamente! ";
      if (scheduleFrequency === "hourly") {
        successMsg += `Se ejecutará cada hora en el minuto ${scheduleMinute}`;
      } else if (scheduleFrequency === "daily") {
        successMsg += `Se ejecutará todos los días a las ${scheduleHour}:${scheduleMinute}`;
      } else if (scheduleFrequency === "weekly") {
        const days = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
        successMsg += `Se ejecutará los ${days[scheduleDayOfWeek]} a las ${scheduleHour}:${scheduleMinute}`;
      }

      setSuccess(successMsg);

      // Notify parent to refresh schedule list
      if (onScheduleCreated) {
        onScheduleCreated();
      }

      // Reset form
      setScheduleName("");
      setScheduleHour("06");
      setScheduleMinute("00");
      setScheduleFrequency("daily");
      setScheduleDayOfWeek(1);
      setScheduleSources([]);

      // Switch back to manual tab after 3 seconds
      setTimeout(() => {
        setActiveTab('manual');
        setSuccess(null);
      }, 3000);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Error al crear la programación"
      );
    } finally {
      setLoading(false);
    }
  };

  // CRON presets
  const cronPresets = [
    { label: "Todos los días a las 6 AM", value: "0 6 * * *" },
    { label: "Todos los días a las 12 PM", value: "0 12 * * *" },
    { label: "Todos los días a las 6 PM", value: "0 18 * * *" },
    { label: "Todos los lunes a las 9 AM", value: "0 9 * * 1" },
    { label: "Cada hora", value: "0 * * * *" },
  ];

  // Status badge color
  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      case "running":
        return "bg-blue-100 text-blue-800";
      case "completed":
        return "bg-green-100 text-green-800";
      case "failed":
        return "bg-red-100 text-red-800";
      case "aborted":
        return "bg-gray-200 text-gray-700";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="space-y-6">
      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Manual and Scheduled Execution Tabs */}
        <div className="bg-white rounded-lg shadow overflow-hidden order-2 lg:order-1">
          <div className="p-6 border-b border-gray-200">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold">Ejecuciones Recientes</h3>
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2">
                  <div className="relative flex items-center justify-center">
                    {/* Pulsing waves */}
                    <span className="absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75 animate-ping"></span>
                    <span className="absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-50 animate-pulse"></span>
                    {/* Core dot */}
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500"></span>
                  </div>
                  <span className="text-xs font-medium text-green-600">LIVE</span>
                </div>
                <Clock />
              </div>
            </div>
          </div>

          {/* Compact Execution List */}
          <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
            {executions.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No se encontraron ejecuciones
              </div>
            ) : (
              executions.slice(0, 10).map((execution) => {
                const duration = execution.duration_seconds !== null
                  ? execution.duration_seconds
                  : (execution.started_at && execution.completed_at
                      ? Math.round(
                          (new Date(execution.completed_at).getTime() -
                            new Date(execution.started_at).getTime()) /
                            1000
                        )
                      : null);

                const dateDisplay = execution.started_at
                  ? new Date(execution.started_at).toLocaleString('es-ES', {
                      day: '2-digit',
                      month: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : new Date(execution.created_at).toLocaleString('es-ES', {
                      day: '2-digit',
                      month: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    });

                const statusTranslations: Record<string, string> = {
                  'pending': 'Pendiente',
                  'running': 'Ejecutando',
                  'completed': 'Completado',
                  'failed': 'Fallido',
                  'aborted': 'Abortado'
                };
                const statusDisplay = statusTranslations[execution.status] || execution.status;

                return (
                  <div
                    key={execution.id}
                  className="p-4 hover:bg-blue-50 transition-colors cursor-pointer border-l-4 border-transparent hover:border-blue-500"
                  onClick={() => setSelectedExecutionId(execution.id)}
                >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-mono text-gray-400">#{execution.id}</span>
                        <span
                          className={`px-2 py-0.5 text-xs font-semibold rounded-full ${getStatusColor(
                            execution.status
                          )}`}
                        >
                          {statusDisplay}
                        </span>
                        {execution.execution_type === 'manual' ? (
                          <span className="text-xs text-gray-500">✋ Manual</span>
                        ) : (
                          <span className="text-xs text-blue-600 font-medium">⏰ {execution.schedule_name || 'Programada'}</span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">{dateDisplay}</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                      {(execution.processed_items > 0 || execution.updated_items > 0 || execution.total_items > 0) && (
                        <div>
                          <span className="text-gray-400">URLs en BD:</span>{" "}
                          <span
                            className="font-medium"
                            title="Total acumulado de URLs en BD para los sources de esta ejecución"
                          >
                            {execution.total_items.toLocaleString('es-ES')}
                          </span>
                          {execution.processed_items > 0 && (
                            <span
                              className="text-green-600 ml-1"
                              title="URLs nuevas añadidas en esta ejecución"
                            >
                              (+{execution.processed_items}
                            </span>
                          )}
                          {execution.updated_items > 0 && (
                            <span
                              className="text-blue-600"
                              title="URLs existentes actualizadas en esta ejecución"
                            >
                              {execution.processed_items > 0 ? ', ~' : '(~'}{execution.updated_items})
                            </span>
                          )}
                          {execution.processed_items === 0 && execution.updated_items === 0 && execution.total_items > 0 && (
                            <span
                              className="text-gray-500 ml-1"
                              title="Sin cambios en la BD"
                            >
                              (sin cambios)
                            </span>
                          )}
                          {execution.failed_items > 0 && (
                            <span className="text-red-600 ml-1">
                              ({execution.failed_items} ✗)
                            </span>
                          )}
                        </div>
                      )}
                      {execution.status === 'completed' && (
                        <div>
                          <span className="text-gray-400">Tokens:</span>{" "}
                          <span className="font-medium">
                            {execution.total_tokens.toLocaleString('es-ES')}
                          </span>
                        </div>
                      )}
                      {execution.status === 'completed' && (
                        <div>
                          <span className="text-gray-400">Costo:</span>{" "}
                          <span className="font-medium">${execution.cost_usd.toFixed(4)}</span>
                        </div>
                      )}
                      {duration !== null && (
                        <div>
                          <span className="text-gray-400">Duración:</span>{" "}
                          <span className="font-medium">{formatDuration(duration)}</span>
                        </div>
                      )}
                    </div>

                    {execution.parameters?.source_names && (
                      <div className="mt-2 text-xs">
                        <span className="text-gray-400">Fuentes:</span>{" "}
                        <span className="text-gray-600">
                          {execution.parameters.source_names.length <= 3
                            ? execution.parameters.source_names.join(', ')
                            : `${execution.parameters.source_names.length} fuentes seleccionadas`}
                        </span>
                      </div>
                    )}

                    {execution.api_keys_used && execution.api_keys_used.length > 0 && (
                      <div className="mt-2 text-xs">
                        <span className="text-gray-400">Claves API usadas:</span>{" "}
                        <div className="flex flex-wrap gap-1 mt-1">
                          {execution.api_keys_used.map((keyId, index) => (
                            <span
                              key={keyId}
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                index === 0
                                  ? 'bg-blue-100 text-blue-800'  // Primary key
                                  : 'bg-yellow-100 text-yellow-800'  // Fallback keys
                              }`}
                              title={index === 0 ? 'Clave principal' : `Fallback #${index}`}
                            >
                              {index === 0 ? '🔑' : '🔄'} {getApiKeyAlias(keyId)}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {execution.error_message && (
                    <div className="mt-2 text-xs text-red-600 bg-red-50 p-2 rounded">
                      ⚠️ {execution.error_message}
                    </div>
                    )}
                    <div className="mt-2 flex items-center gap-3">
                      <button
                        onClick={() => setSelectedExecutionId(execution.id)}
                        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
                      >
                        <Eye size={16} />
                        Ver Detalles
                      </button>
                      {(execution.status === 'running' || execution.status === 'pending') && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAbort(execution.id);
                          }}
                          className="text-sm text-red-600 hover:text-red-800 font-medium"
                        >
                          Abortar
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Manual and Scheduled Execution Tabs */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {/* Tabs */}
          <div className="border-b border-gray-200">
            <div className="flex">
              <button
                onClick={() => setActiveTab('manual')}
                className={`flex-1 px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'manual'
                    ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
                }`}
              >
                🚀 Ejecución Manual
              </button>
              <button
                onClick={() => setActiveTab('scheduled')}
                className={`flex-1 px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'scheduled'
                    ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
                }`}
              >
                ⏰ Nueva Programación
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === 'manual' ? (
              // Manual Execution Form
              <div className="space-y-4">
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

                {/* API Key Selector */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Clave API
                  </label>
                  <select
                    value={selectedApiKey || ""}
                    onChange={(e) => setSelectedApiKey(Number(e.target.value))}
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

                {/* Fallback Toggle */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <label className="flex items-start space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={useFallback}
                      onChange={(e) => setUseFallback(e.target.checked)}
                      disabled={loading}
                      className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">
                        🔄 Habilitar claves de fallback automático
                      </div>
                      <p className="text-sm text-gray-600 mt-1">
                        Si está activado y la clave seleccionada se queda sin créditos,
                        el sistema usará automáticamente otras claves disponibles como respaldo.
                      </p>
                      <p className="text-xs text-gray-500 mt-2">
                        {useFallback ? (
                          <span className="text-green-600">✓ Fallback habilitado - Máxima disponibilidad</span>
                        ) : (
                          <span className="text-orange-600">⚠️ Fallback deshabilitado - Solo se usará la clave seleccionada</span>
                        )}
                      </p>
                    </div>
                  </label>
                </div>

                {/* Source Filter */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Fuentes (opcional - dejar vacío para todas)
                  </label>
                  <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-3 border border-gray-300 rounded">
                    {sources.map((source) => (
                      <label
                        key={source.id}
                        className="flex items-center space-x-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedSources.includes(source.name)}
                          onChange={() => toggleSource(source.name)}
                          disabled={loading}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-700">{source.name}</span>
                      </label>
                    ))}
                  </div>
                  {selectedSources.length > 0 && (
                    <p className="text-sm text-gray-500 mt-2">
                      Seleccionadas: {selectedSources.length} fuente(s)
                    </p>
                  )}
                </div>

                {/* Execute Button */}
                <button
                  onClick={handleExecute}
                  disabled={loading || !selectedApiKey || hasRunningExecution}
                  className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  {loading
                    ? "Iniciando..."
                    : hasRunningExecution
                    ? "Ejecución en Curso..."
                    : "Ejecutar Ahora"}
                </button>
              </div>
            ) : (
              // Schedule Creation Form
              <div className="space-y-4">
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

                {/* Schedule Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Nombre de Programación *
                  </label>
                  <input
                    type="text"
                    value={scheduleName}
                    onChange={(e) => setScheduleName(e.target.value)}
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
                      onClick={() => setScheduleFrequency("hourly")}
                      className={`p-3 border-2 rounded-lg transition-all ${
                        scheduleFrequency === "hourly"
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
                      onClick={() => setScheduleFrequency("daily")}
                      className={`p-3 border-2 rounded-lg transition-all ${
                        scheduleFrequency === "daily"
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
                      onClick={() => setScheduleFrequency("weekly")}
                      className={`p-3 border-2 rounded-lg transition-all ${
                        scheduleFrequency === "weekly"
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
                {scheduleFrequency === "weekly" && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Día de la Semana *
                    </label>
                    <select
                      value={scheduleDayOfWeek}
                      onChange={(e) => setScheduleDayOfWeek(Number(e.target.value))}
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
                {scheduleFrequency !== "hourly" ? (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Hora de Ejecución *
                    </label>
                    <div className="flex space-x-3 items-center">
                      <select
                        value={scheduleHour}
                        onChange={(e) => setScheduleHour(e.target.value)}
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
                        value={scheduleMinute}
                        onChange={(e) => setScheduleMinute(e.target.value)}
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
                      value={scheduleMinute}
                      onChange={(e) => setScheduleMinute(e.target.value)}
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
                      Se ejecutará cada hora en el minuto {scheduleMinute}
                    </p>
                  </div>
                )}

                {/* API Key */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Clave API *
                  </label>
                  <select
                    value={scheduleApiKey || ""}
                    onChange={(e) => setScheduleApiKey(Number(e.target.value))}
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
                  <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-3 border border-gray-300 rounded">
                    {sources.map((source) => (
                      <label
                        key={source.id}
                        className="flex items-center space-x-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={scheduleSources.includes(source.name)}
                          onChange={() => toggleScheduleSource(source.name)}
                          disabled={loading}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-700">{source.name}</span>
                      </label>
                    ))}
                  </div>
                  {scheduleSources.length > 0 && (
                    <p className="text-sm text-gray-500 mt-2">
                      Seleccionadas: {scheduleSources.length} fuente(s)
                    </p>
                  )}
                </div>

                {/* Create Button */}
                <button
                  onClick={handleCreateSchedule}
                  disabled={loading || !scheduleName || !scheduleApiKey}
                  className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  {loading ? "Creando..." : "✨ Crear Programación"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Execution Detail Modal */}
      {selectedExecutionId !== null && (
        <ExecutionDetailModal
          executionId={selectedExecutionId}
          onClose={() => setSelectedExecutionId(null)}
        />
      )}
    </div>
  );
}
