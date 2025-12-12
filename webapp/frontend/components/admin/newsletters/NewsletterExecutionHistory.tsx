"use client";

import { useState, useEffect, ReactNode } from "react";
import { apiClient } from "@/lib/api-client";
import {
  Loader2,
  Play,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  Eye,
  RefreshCw,
} from "lucide-react";
import NewsletterStageProgress from "./NewsletterStageProgress";
import { useNewsletterConfigs } from "@/contexts/NewsletterConfigsContext";

// Clock component
function ClockWidget() {
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

interface NewsletterExecution {
  id: number;
  newsletter_config_name?: string | null;
  status: "pending" | "running" | "completed" | "failed" | "queued";
  run_date: string;
  execution_type: "manual" | "scheduled";
  api_key_alias?: string | null;
  total_stages: number;
  completed_stages: number;
  failed_stages: number;
  api_key_id?: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  total_tokens?: number;
  created_at: string;
  duration_seconds: number | null;
  error_message: string | null;
}

interface NewsletterConfig {
  id: number;
  name: string;
  display_name: string | null;
  is_active: boolean;
}

interface APIKey {
  id: number;
  alias: string;
}

interface StageExecution {
  id: number;
  stage_number: number;
  stage_name: string;
  status: "pending" | "running" | "completed" | "failed" | "aborted";
  items_processed: number;
  items_successful: number;
  items_failed: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  duration_seconds: number | null;
  error_message: string | null;
}

interface NewsletterSchedule {
  id: number;
  name: string;
  newsletter_config_id: number;
  cron_expression: string;
  api_key_id: number;
  trigger_on_stage1_ready?: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  next_run_at: string | null;
}

type ScheduleFrequency = "daily" | "weekly" | "hourly" | "interval";

interface NewsletterExecutionHistoryProps {
  afterMainContent?: ReactNode;
}

export default function NewsletterExecutionHistory({ afterMainContent }: NewsletterExecutionHistoryProps) {
  const { configs } = useNewsletterConfigs();
  const [executions, setExecutions] = useState<NewsletterExecution[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [schedules, setSchedules] = useState<NewsletterSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<"manual" | "schedule">("manual");
  const [selectedExecution, setSelectedExecution] =
    useState<NewsletterExecution | null>(null);
  const [stageDetails, setStageDetails] = useState<StageExecution[]>([]);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showEditScheduleModal, setShowEditScheduleModal] = useState(false);
  const [editingScheduleId, setEditingScheduleId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Manual execution form
  const [manualForm, setManualForm] = useState({
    newsletter_config_id: 0,
    run_date: new Date().toISOString().split("T")[0],
    api_key_id: 0,
    force: false,
  });
  const [advancedMode, setAdvancedMode] = useState(false);

  // Schedule form
  const [scheduleForm, setScheduleForm] = useState({
    name: "",
    newsletter_config_id: 0,
    frequency: "daily" as ScheduleFrequency,
    hour: "06",
    minute: "00",
    dayOfWeek: 1,
    intervalMinutes: "30",
    api_key_id: 0,
    trigger_on_stage1_ready: false,
    is_active: true,
  });

  // Edit schedule form
  const [editScheduleForm, setEditScheduleForm] = useState({
    name: "",
    newsletter_config_id: 0,
    frequency: "daily" as ScheduleFrequency,
    hour: "06",
    minute: "00",
    dayOfWeek: 1,
    intervalMinutes: "30",
    api_key_id: 0,
    trigger_on_stage1_ready: false,
  });

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      loadExecutions(); // Poll every 3s for updates
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Update form defaults when configs change
  useEffect(() => {
    if (configs.length > 0) {
      setManualForm((prev) => ({
        ...prev,
        newsletter_config_id: prev.newsletter_config_id || configs[0].id,
      }));
      setScheduleForm((prev) => ({
        ...prev,
        newsletter_config_id: prev.newsletter_config_id || configs[0].id,
      }));
    }
  }, [configs]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [executionsRes, apiKeysRes, schedulesRes] = await Promise.all([
        apiClient.get("/newsletter-executions?limit=10"),
        apiClient.get("/api-keys"),
        apiClient.get("/scheduled-executions?execution_type=newsletter_pipeline"),
      ]);
      setExecutions(executionsRes.data || []);
      setApiKeys(apiKeysRes.data?.api_keys || []);
      setSchedules(schedulesRes.data || []);

      // Set API key defaults
      if (apiKeysRes.data?.api_keys && apiKeysRes.data.api_keys.length > 0) {
        setManualForm((prev) => ({
          ...prev,
          api_key_id: apiKeysRes.data.api_keys[0].id,
        }));
        setScheduleForm((prev) => ({
          ...prev,
          api_key_id: apiKeysRes.data.api_keys[0].id,
        }));
      }
    } catch (err) {
      console.error("Error loading data:", err);
      // Set empty arrays on error
      setExecutions([]);
      setApiKeys([]);
      setSchedules([]);
    } finally {
      setLoading(false);
    }
  };

  const loadExecutions = async () => {
    try {
      const response = await apiClient.get("/newsletter-executions?limit=10");
      setExecutions(response.data);
    } catch (err) {
      console.error("Error refreshing executions:", err);
    }
  };

  const loadSchedules = async () => {
    try {
      const response = await apiClient.get("/scheduled-executions?execution_type=newsletter_pipeline");
      setSchedules(response.data || []);
    } catch (err) {
      console.error("Error refreshing schedules:", err);
    }
  };

  // Parse CRON to human-readable format
  const parseCronToHumanReadable = (cronExpression: string): { frequency: string; time: string } => {
    const parts = cronExpression.split(' ');
    if (parts.length !== 5) {
      return { frequency: 'Desconocido', time: cronExpression };
    }

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    if (minute.startsWith("*/")) {
      const interval = minute.replace("*/", "");
      return { frequency: `⏱️ Cada ${interval} min`, time: "-" };
    }

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
    frequency: ScheduleFrequency;
    hour: string;
    minute: string;
    dayOfWeek: number;
    intervalMinutes: string;
  } => {
    const parts = cronExpression.split(' ');
    if (parts.length !== 5) {
      return { frequency: 'daily', hour: '06', minute: '00', dayOfWeek: 1, intervalMinutes: "30" };
    }

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    if (minute.startsWith("*/")) {
      const intervalVal = minute.replace("*/", "") || "30";
      return {
        frequency: "interval",
        hour: "00",
        minute: "00",
        dayOfWeek: 1,
        intervalMinutes: intervalVal
      };
    }

    // Determine frequency
    let frequency: ScheduleFrequency = "daily";
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
      localMinute = minute.padStart(2, '0');
    }

    const parsedDayOfWeek = dayOfWeek !== '*' ? parseInt(dayOfWeek) : 1;

      return {
        frequency,
        hour: localHour,
        minute: localMinute,
        dayOfWeek: parsedDayOfWeek,
        intervalMinutes: "30"
      };
  };

  // Convert local time to UTC CRON expression
  const convertToUTCCron = (
    frequency: ScheduleFrequency,
    localHour: string,
    localMinute: string,
    dayOfWeek?: number,
    intervalMinutes?: string
  ): string => {
    if (frequency === "interval") {
      const minutes = Math.max(1, parseInt(intervalMinutes || "1"));
      return `*/${minutes} * * * *`;
    }

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

  const handleManualExecution = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setFeedback(null);
      await apiClient.post("/newsletter-executions", manualForm);
      setFeedback({ type: "success", message: "Ejecución iniciada correctamente" });
      loadExecutions();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.response?.data?.detail || "Error al iniciar ejecución",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleScheduleCreation = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setFeedback(null);
      const cron_expression = convertToUTCCron(
        scheduleForm.frequency,
        scheduleForm.hour,
        scheduleForm.minute,
        scheduleForm.dayOfWeek,
        scheduleForm.intervalMinutes
      );
      await apiClient.post("/scheduled-executions", {
        ...scheduleForm,
        cron_expression,
        execution_target: "newsletter_pipeline",
      });
      setFeedback({ type: "success", message: "Programación creada correctamente" });
      setScheduleForm({
        name: "",
        newsletter_config_id: configs[0]?.id || 0,
        frequency: "daily",
        hour: "06",
        minute: "00",
        dayOfWeek: 1,
        intervalMinutes: "30",
        api_key_id: apiKeys[0]?.id || 0,
        trigger_on_stage1_ready: false,
        is_active: true,
      });
      loadSchedules();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.response?.data?.detail || "Error al crear programación",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditSchedule = (schedule: NewsletterSchedule) => {
    setEditingScheduleId(schedule.id);
    const { frequency, hour, minute, dayOfWeek, intervalMinutes } = parseCronToFormValues(schedule.cron_expression);
    setEditScheduleForm({
      name: schedule.name,
      newsletter_config_id: schedule.newsletter_config_id,
      frequency,
      hour,
      minute,
      dayOfWeek,
      intervalMinutes,
      api_key_id: schedule.api_key_id,
      trigger_on_stage1_ready: !!schedule.trigger_on_stage1_ready,
    });
    setShowEditScheduleModal(true);
  };

  const handleUpdateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingScheduleId) return;

    try {
      setSubmitting(true);
      setFeedback(null);
      const cronExpression = convertToUTCCron(
        editScheduleForm.frequency,
        editScheduleForm.hour,
        editScheduleForm.minute,
        editScheduleForm.dayOfWeek,
        editScheduleForm.intervalMinutes
      );

      const payload = {
        name: editScheduleForm.name,
        newsletter_config_id: editScheduleForm.newsletter_config_id,
        cron_expression: cronExpression,
        api_key_id: editScheduleForm.api_key_id,
        trigger_on_stage1_ready: editScheduleForm.trigger_on_stage1_ready,
        is_active: true,
        execution_target: "newsletter_pipeline",
      };

      console.log('🔍 Sending schedule update:', payload);
      console.log('🔍 trigger_on_stage1_ready value:', editScheduleForm.trigger_on_stage1_ready, typeof editScheduleForm.trigger_on_stage1_ready);

      await apiClient.put(`/scheduled-executions/${editingScheduleId}`, payload);
      setFeedback({ type: "success", message: "Programación actualizada correctamente" });
      setShowEditScheduleModal(false);
      setEditingScheduleId(null);
      loadSchedules();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.response?.data?.detail || "Error al actualizar programación",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleSchedule = async (id: number) => {
    try {
      setFeedback(null);
      await apiClient.put(`/scheduled-executions/${id}/toggle`);
      setFeedback({ type: "success", message: "Estado de la programación actualizado" });
      loadSchedules();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: "Error al cambiar el estado de la programación",
      });
    }
  };

  const handleDeleteSchedule = async (id: number, name: string) => {
    if (!confirm(`¿Estás seguro de que deseas eliminar la programación "${name}"?`)) {
      return;
    }

    try {
      await apiClient.delete(`/scheduled-executions/${id}`);
      setFeedback({ type: "success", message: "Programación eliminada correctamente" });
      loadSchedules();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: "Error al eliminar la programación",
      });
    }
  };

  const handleViewDetails = async (execution: NewsletterExecution) => {
    try {
      setFeedback(null);
      const stagesResponse = await apiClient.get(
        `/newsletter-executions/${execution.id}/stages`
      );
      const execResponse = await apiClient.get(
        `/newsletter-executions/${execution.id}`
      );
      setStageDetails(stagesResponse.data);
      setSelectedExecution(execResponse.data);
      setShowDetailModal(true);
    } catch (err) {
      console.error("Error loading stage details:", err);
      setFeedback({
        type: "error",
        message: "Error al cargar detalles de stages",
      });
    }
  };

  const handleAbortExecution = async (executionId: number) => {
    try {
      setSubmitting(true);
      setFeedback(null);
      await apiClient.post(`/newsletter-executions/${executionId}/abort`);
      await loadExecutions();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.response?.data?.detail || "No se pudo abortar la ejecución",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetryExecution = async (executionId: number) => {
    try {
      setSubmitting(true);
      setFeedback(null);
      const response = await apiClient.post(`/newsletter-executions/${executionId}/retry`);
      setFeedback({
        type: "success",
        message: `Reintento creado correctamente (ID: ${response.data.id})`,
      });
      await loadExecutions();
    } catch (err: any) {
      setFeedback({
        type: "error",
        message: err.response?.data?.detail || "No se pudo reintentar la ejecución",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Refresh stage details (for polling)
  const refreshStageDetails = async (executionId: number) => {
    try {
      setIsRefreshing(true);
      const response = await apiClient.get(
        `/newsletter-executions/${executionId}/stages`
      );
      setStageDetails(response.data);

      // Also refresh the execution status in the main list
      const execResponse = await apiClient.get(
        `/newsletter-executions/${executionId}`
      );
      setSelectedExecution(execResponse.data);
    } catch (err) {
      console.error("Error refreshing stage details:", err);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Auto-refresh when modal is open and execution is running
  useEffect(() => {
    if (!showDetailModal || !selectedExecution) return;

    // Only poll if execution is running, pending, or queued
    if (!["running", "pending", "queued"].includes(selectedExecution.status)) return;

    const pollInterval = setInterval(() => {
      refreshStageDetails(selectedExecution.id);
    }, 3000); // Refresh every 3 seconds

    return () => clearInterval(pollInterval);
  }, [showDetailModal, selectedExecution]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
            <CheckCircle size={14} />
            Completado
          </span>
        );
      case "running":
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
            <Loader2 size={14} className="animate-spin" />
            Ejecutando
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">
            <XCircle size={14} />
            Error
          </span>
        );
      case "aborted":
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium">
            <XCircle size={14} />
            Abortado
          </span>
        );
      case "pending":
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm font-medium">
            <Clock size={14} />
            Pendiente
          </span>
        );
      case "queued":
        return (
          <span className="flex items-center gap-1 px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-sm font-medium">
            <Clock size={14} />
            En cola
          </span>
        );
      default:
        return null;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "-";
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  const stageAggregates = stageDetails.reduce(
    (acc, stage) => {
      const input = stage.input_tokens ?? 0;
      const output = stage.output_tokens ?? 0;
      const tokens =
        stage.total_tokens !== undefined
          ? stage.total_tokens
          : input + output;
      return {
        tokens: acc.tokens + (tokens ?? 0),
        cost: acc.cost + (stage.cost_usd ?? 0),
        input: acc.input + input,
        output: acc.output + output,
      };
    },
    { tokens: 0, cost: 0, input: 0, output: 0 }
  );

  const selectedExecutionTotalTokens = selectedExecution
    ? (() => {
        const totals =
          (selectedExecution.total_tokens ??
            (selectedExecution.total_input_tokens ?? 0) +
              (selectedExecution.total_output_tokens ?? 0)) ?? 0;
        return totals > 0 ? totals : stageAggregates.tokens;
      })()
    : stageAggregates.tokens;

  const selectedExecutionInputTokens = selectedExecution
    ? (() => {
        const input = selectedExecution.total_input_tokens ?? 0;
        return input > 0 ? input : stageAggregates.input;
      })()
    : stageAggregates.input;

  const selectedExecutionOutputTokens = selectedExecution
    ? (() => {
        const output = selectedExecution.total_output_tokens ?? 0;
        return output > 0 ? output : stageAggregates.output;
      })()
    : stageAggregates.output;

  const selectedExecutionCost = selectedExecution
    ? (() => {
        const cost = selectedExecution.total_cost_usd ?? 0;
        return cost > 0 ? cost : stageAggregates.cost;
      })()
    : stageAggregates.cost;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-blue-600" size={48} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">
          Ejecuciones de Newsletters
        </h2>
        <p className="text-gray-600 mt-1">
          Historial de ejecuciones y lanzamiento manual/programado
        </p>
      </div>

      {feedback && (
        <div
          className={`p-3 border rounded ${
            feedback.type === "success"
              ? "bg-green-50 border-green-200 text-green-700"
              : "bg-red-50 border-red-200 text-red-700"
          }`}
        >
          {feedback.message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Execution History */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-900">
                Últimas Ejecuciones
              </h3>
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
                <ClockWidget />
              </div>
            </div>
          </div>

          <div className="divide-y max-h-[600px] overflow-y-auto">
            {executions.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No hay ejecuciones registradas
              </div>
            ) : (
              executions.map((execution) => {
                const totalTokens = (execution.total_input_tokens ?? 0) + (execution.total_output_tokens ?? 0);
                const totalCost = execution.total_cost_usd ?? 0;
                return (
                <div
                  key={execution.id}
                  className="p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-medium text-gray-900">
                        {execution.newsletter_config_name || "(Config eliminada)"}
                      </div>
                      <div className="text-sm text-gray-500">
                        ID: {execution.id} • {execution.execution_type === "manual" ? "Manual" : "Programada"}
                      </div>
                    </div>
                    {getStatusBadge(execution.status)}
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                    <div>
                      <span className="text-gray-600">Ejecutada:</span>
                      <span className="ml-2 font-medium">
                        {new Date(execution.created_at).toLocaleString('es-ES', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Duración:</span>
                      <span className="ml-2 font-medium">
                        {formatDuration(execution.duration_seconds)}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Tokens:</span>
                      <span className="ml-2 font-medium">
                        {totalTokens.toLocaleString("es-ES")}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Costo:</span>
                      <span className="ml-2 font-medium">
                        ${totalCost.toFixed(4)}
                      </span>
                    </div>
                    <div className="col-span-2">
                      <span className="text-gray-600">Progreso:</span>
                      <span className="ml-2 font-medium">
                        {execution.completed_stages}/{execution.total_stages}{" "}
                        stages
                      </span>
                      <div className="mt-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${
                            execution.status === "failed"
                              ? "bg-red-500"
                              : execution.status === "completed"
                              ? "bg-green-500"
                              : "bg-blue-500"
                          } transition-all`}
                          style={{
                            width: `${
                              (execution.completed_stages /
                                execution.total_stages) *
                              100
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  {execution.error_message && (
                    <div className="text-sm text-red-600 mb-2 p-2 bg-red-50 rounded">
                      Error: {execution.error_message}
                    </div>
                  )}

                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleViewDetails(execution)}
                      className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      <Eye size={16} />
                      Ver Detalles
                    </button>
                    {execution.status === "failed" && (
                      <button
                        onClick={() => handleRetryExecution(execution.id)}
                        disabled={submitting}
                        className="flex items-center gap-2 text-sm text-green-600 hover:text-green-800 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <RefreshCw size={16} />
                        Reintentar
                      </button>
                    )}
                    {(execution.status === "running" || execution.status === "pending" || execution.status === "queued") && (
                      <button
                        onClick={() => handleAbortExecution(execution.id)}
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

        {/* Right Column: Action Forms */}
        <div className="bg-white rounded-lg shadow">
          {/* Tabs */}
          <div className="flex border-b">
            <button
              onClick={() => setActiveTab("manual")}
              className={`flex-1 px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === "manual"
                  ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <Play size={18} />
                Ejecución Manual
              </div>
            </button>
            <button
              onClick={() => setActiveTab("schedule")}
              className={`flex-1 px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === "schedule"
                  ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <Calendar size={18} />
                Programar Ejecución
              </div>
            </button>
          </div>

          <div className="p-6">
            {activeTab === "manual" ? (
              <form onSubmit={handleManualExecution} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Newsletter
                  </label>
                  <select
                    required
                    value={manualForm.newsletter_config_id}
                    onChange={(e) =>
                      setManualForm({
                        ...manualForm,
                        newsletter_config_id: parseInt(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {configs.map((config) => (
                      <option key={config.id} value={config.id}>
                        {config.display_name || config.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    API Key
                  </label>
                  <select
                    required
                    value={manualForm.api_key_id}
                    onChange={(e) =>
                      setManualForm({
                        ...manualForm,
                        api_key_id: parseInt(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {apiKeys.map((key) => (
                      <option key={key.id} value={key.id}>
                        {key.alias}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Advanced Mode Toggle */}
                <div className="border-t pt-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={advancedMode}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setAdvancedMode(checked);
                        // Reset to today when exiting advanced mode
                        if (!checked) {
                          setManualForm({
                            ...manualForm,
                            run_date: new Date().toISOString().split("T")[0]
                          });
                        }
                      }}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <div>
                      <span className="text-sm font-medium text-gray-700">
                        Modo Avanzado
                      </span>
                      <p className="text-xs text-gray-500">
                        Permite seleccionar fecha personalizada
                      </p>
                    </div>
                  </label>
                </div>

                {/* Date Selector - Only in Advanced Mode */}
                {advancedMode && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Fecha de Ejecución
                    </label>
                    <input
                      type="date"
                      required
                      value={manualForm.run_date}
                      onChange={(e) =>
                        setManualForm({ ...manualForm, run_date: e.target.value })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-yellow-600 mt-1">
                      ⚠️ Solo funcionará si existe scraping (Stage 1) para esta fecha
                    </p>
                  </div>
                )}

                {/* Show current date when not in advanced mode */}
                {!advancedMode && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <p className="text-sm text-blue-800">
                      📅 Fecha de ejecución: <span className="font-semibold">Hoy ({new Date().toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' })})</span>
                    </p>
                  </div>
                )}

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={manualForm.force}
                    onChange={(e) =>
                      setManualForm({ ...manualForm, force: e.target.checked })
                    }
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">
                    Forzar re-ejecución (ignorar cache)
                  </span>
                </label>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={20} className="animate-spin" />
                      Iniciando...
                    </>
                  ) : (
                    <>
                      <Play size={20} />
                      Ejecutar Ahora
                    </>
                  )}
                </button>
              </form>
            ) : (
              <div className="space-y-6">
                {/* Schedule Form - Create Mode Only */}
                <form onSubmit={handleScheduleCreation} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Nombre de la Programación *
                    </label>
                    <input
                      type="text"
                      required
                      value={scheduleForm.name}
                      onChange={(e) =>
                        setScheduleForm({ ...scheduleForm, name: e.target.value })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Newsletter Diaria Economía"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Newsletter
                    </label>
                    <select
                      required
                      value={scheduleForm.newsletter_config_id}
                      onChange={(e) =>
                        setScheduleForm({ ...scheduleForm, newsletter_config_id: parseInt(e.target.value) })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {configs.map((config) => (
                        <option key={config.id} value={config.id}>
                          {config.display_name || config.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Frequency and time */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Frecuencia *
                      </label>
                      <select
                        value={scheduleForm.frequency}
                        onChange={(e) =>
                          setScheduleForm({
                            ...scheduleForm,
                            frequency: e.target.value as ScheduleFrequency,
                          })
                        }
                        className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="daily">Diaria</option>
                        <option value="weekly">Semanal</option>
                        <option value="hourly">Cada hora</option>
                        <option value="interval">Cada X minutos</option>
                      </select>
                    </div>

                  {scheduleForm.frequency === "interval" ? (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Cada cuántos minutos
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="1440"
                        value={scheduleForm.intervalMinutes}
                        onChange={(e) =>
                          setScheduleForm({ ...scheduleForm, intervalMinutes: e.target.value })
                        }
                        className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Se intentará lanzar en ese intervalo, solo si el Stage 1 del día ya está listo.
                      </p>
                    </div>
                  ) : scheduleForm.frequency === "hourly" ? (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Minuto de Ejecución *
                      </label>
                      <select
                        value={scheduleForm.minute}
                        onChange={(e) =>
                          setScheduleForm({ ...scheduleForm, minute: e.target.value })
                        }
                        className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
                      >
                        {Array.from({ length: 60 }, (_, i) => i).map((minute) => (
                          <option key={minute} value={minute.toString().padStart(2, '0')}>
                            {minute.toString().padStart(2, '0')}
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-gray-500 mt-1 text-center">
                        Se ejecutará cada hora en el minuto {scheduleForm.minute}
                      </p>
                    </div>
                  ) : (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Hora de Ejecución *
                      </label>
                      <div className="flex space-x-3 items-center">
                        <select
                          value={scheduleForm.hour}
                          onChange={(e) =>
                            setScheduleForm({ ...scheduleForm, hour: e.target.value })
                          }
                          className="flex-1 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
                        >
                          {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
                            <option key={hour} value={hour.toString().padStart(2, '0')}>
                              {hour.toString().padStart(2, '0')}
                            </option>
                          ))}
                        </select>
                        <span className="text-2xl text-gray-400">:</span>
                        <select
                          value={scheduleForm.minute}
                          onChange={(e) =>
                            setScheduleForm({ ...scheduleForm, minute: e.target.value })
                          }
                          className="flex-1 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
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
                  )}
                  </div>

                  {scheduleForm.frequency === "weekly" && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Día de la semana
                      </label>
                      <select
                        value={scheduleForm.dayOfWeek}
                        onChange={(e) =>
                          setScheduleForm({
                            ...scheduleForm,
                            dayOfWeek: parseInt(e.target.value),
                          })
                        }
                        className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"].map(
                          (day, idx) => (
                            <option key={day} value={idx}>
                              {day}
                            </option>
                          )
                        )}
                      </select>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API Key
                    </label>
                    <select
                      required
                      value={scheduleForm.api_key_id}
                      onChange={(e) =>
                        setScheduleForm({ ...scheduleForm, api_key_id: parseInt(e.target.value) })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {apiKeys.map((key) => (
                        <option key={key.id} value={key.id}>
                          {key.alias}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-start gap-3 p-3 border rounded-lg bg-gray-50">
                    <input
                      type="checkbox"
                      id="trigger_stage1_ready"
                      className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      checked={scheduleForm.trigger_on_stage1_ready}
                      onChange={(e) =>
                        setScheduleForm({
                          ...scheduleForm,
                          trigger_on_stage1_ready: e.target.checked,
                        })
                      }
                    />
                    <div>
                      <label
                        htmlFor="trigger_stage1_ready"
                        className="text-sm font-medium text-gray-800"
                      >
                        Lanzar en cuanto Stage 1 del día esté listo
                      </label>
                      <p className="text-xs text-gray-600 mt-1">
                        Usa el cron solo para elegir el día (diario/semanal). El envío arrancará tan pronto acabe el scraping Stage 1 para las fuentes del newsletter.
                      </p>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitting ? (
                      <>
                        <Loader2 size={20} className="animate-spin" />
                        Creando...
                      </>
                    ) : (
                      <>
                        <Calendar size={20} />
                        Crear Programación
                      </>
                    )}
                  </button>
                </form>
              </div>
            )}
        </div>
      </div>
    </div>

    {afterMainContent && (
      <div className="space-y-6">
        {afterMainContent}
      </div>
    )}

    {/* Scheduled Executions List */}
    <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-gray-900">
              Ejecuciones Programadas
            </h3>
            <button
              onClick={loadSchedules}
              className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700"
            >
              <RefreshCw size={16} />
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
                  Newsletter
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Modo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Periodicidad
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hora
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
                  <td colSpan={8} className="px-6 py-4 text-center text-gray-500">
                    No se encontraron programaciones
                  </td>
                </tr>
              ) : (
                schedules.map((schedule) => {
                  const { frequency, time } = parseCronToHumanReadable(schedule.cron_expression);
                  const config = configs.find(c => c.id === schedule.newsletter_config_id);
                  return (
                    <tr key={schedule.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {schedule.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {config?.display_name || config?.name || 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-2 py-1 text-xs font-semibold rounded-full ${
                            schedule.trigger_on_stage1_ready
                              ? "bg-indigo-100 text-indigo-800"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {schedule.trigger_on_stage1_ready ? "Stage 1 Ready" : "Hora fija"}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                        {frequency}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 font-medium">
                        {time}
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
                          onClick={() => handleEditSchedule(schedule)}
                          className="text-indigo-600 hover:text-indigo-700 font-medium"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => handleToggleSchedule(schedule.id)}
                          className="text-blue-600 hover:text-blue-700 font-medium"
                        >
                          {schedule.is_active ? "Desactivar" : "Activar"}
                        </button>
                        <button
                          onClick={() => handleDeleteSchedule(schedule.id, schedule.name)}
                          className="text-red-600 hover:text-red-700 font-medium"
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

      {/* Edit Schedule Modal */}
      {showEditScheduleModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-xl">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Editar programación</h3>
                <p className="text-sm text-gray-500">Actualiza hora, API key o modo de disparo</p>
              </div>
              <button
                onClick={() => {
                  setShowEditScheduleModal(false);
                  setEditingScheduleId(null);
                }}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleUpdateSchedule} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nombre
                </label>
                <input
                  type="text"
                  required
                  value={editScheduleForm.name}
                  onChange={(e) =>
                    setEditScheduleForm({ ...editScheduleForm, name: e.target.value })
                  }
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Newsletter
                  </label>
                  <select
                    required
                    value={editScheduleForm.newsletter_config_id}
                    onChange={(e) =>
                      setEditScheduleForm({
                        ...editScheduleForm,
                        newsletter_config_id: parseInt(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {configs.map((config) => (
                      <option key={config.id} value={config.id}>
                        {config.display_name || config.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    API Key
                  </label>
                  <select
                    required
                    value={editScheduleForm.api_key_id}
                    onChange={(e) =>
                      setEditScheduleForm({
                        ...editScheduleForm,
                        api_key_id: parseInt(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {apiKeys.map((key) => (
                      <option key={key.id} value={key.id}>
                        {key.alias}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Frecuencia
                  </label>
                  <select
                    value={editScheduleForm.frequency}
                    onChange={(e) =>
                      setEditScheduleForm({
                        ...editScheduleForm,
                        frequency: e.target.value as ScheduleFrequency,
                      })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="daily">Diaria</option>
                    <option value="weekly">Semanal</option>
                    <option value="hourly">Cada hora</option>
                    <option value="interval">Cada X minutos</option>
                  </select>
                </div>

                {editScheduleForm.frequency === "interval" ? (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Cada cuántos minutos
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="1440"
                      value={editScheduleForm.intervalMinutes}
                      onChange={(e) =>
                        setEditScheduleForm({ ...editScheduleForm, intervalMinutes: e.target.value })
                      }
                      className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Se intentará lanzar en ese intervalo, solo si el Stage 1 del día ya está listo.
                    </p>
                  </div>
                ) : editScheduleForm.frequency === "hourly" ? (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Minuto de Ejecución *
                    </label>
                    <select
                      value={editScheduleForm.minute}
                      onChange={(e) =>
                        setEditScheduleForm({ ...editScheduleForm, minute: e.target.value })
                      }
                      className="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
                    >
                      {Array.from({ length: 60 }, (_, i) => i).map((minute) => (
                        <option key={minute} value={minute.toString().padStart(2, '0')}>
                          {minute.toString().padStart(2, '0')}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-500 mt-1 text-center">
                      Se ejecutará cada hora en el minuto {editScheduleForm.minute}
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Hora de Ejecución *
                    </label>
                    <div className="flex space-x-3 items-center">
                      <select
                        value={editScheduleForm.hour}
                        onChange={(e) =>
                          setEditScheduleForm({ ...editScheduleForm, hour: e.target.value })
                        }
                        className="flex-1 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
                      >
                        {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
                          <option key={hour} value={hour.toString().padStart(2, '0')}>
                            {hour.toString().padStart(2, '0')}
                          </option>
                        ))}
                      </select>
                      <span className="text-2xl text-gray-400">:</span>
                      <select
                        value={editScheduleForm.minute}
                        onChange={(e) =>
                          setEditScheduleForm({ ...editScheduleForm, minute: e.target.value })
                        }
                        className="flex-1 p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-center text-lg"
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
                )}
              </div>

              {editScheduleForm.frequency === "weekly" && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Día de la semana
                  </label>
                  <select
                    value={editScheduleForm.dayOfWeek}
                    onChange={(e) =>
                      setEditScheduleForm({
                        ...editScheduleForm,
                        dayOfWeek: parseInt(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"].map(
                      (day, idx) => (
                        <option key={day} value={idx}>
                          {day}
                        </option>
                      )
                    )}
                  </select>
                </div>
              )}

              <div className="flex items-start gap-3 p-3 border rounded-lg bg-gray-50">
                <input
                  type="checkbox"
                  id="edit_trigger_stage1_ready"
                  className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  checked={editScheduleForm.trigger_on_stage1_ready}
                  onChange={(e) =>
                    setEditScheduleForm({
                      ...editScheduleForm,
                      trigger_on_stage1_ready: e.target.checked,
                    })
                  }
                />
                <div>
                  <label
                    htmlFor="edit_trigger_stage1_ready"
                    className="text-sm font-medium text-gray-800"
                  >
                    Lanzar en cuanto Stage 1 del día esté listo
                  </label>
                  <p className="text-xs text-gray-600 mt-1">
                    Respeta los días definidos por el cron y evita esperar a la hora exacta si ya hay scraping válido.
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowEditScheduleModal(false);
                    setEditingScheduleId(null);
                  }}
                  className="px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedExecution && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">
                    Detalles de Ejecución #{selectedExecution.id}
                  </h3>
                  <p className="text-sm text-gray-600">
                    {selectedExecution.newsletter_config_name || "(Config eliminada)"} •{" "}
                    {selectedExecution.run_date}
                  </p>
                </div>
                {selectedExecution.status === "running" && (
                  <div className="flex items-center gap-2 px-3 py-1 bg-blue-50 border border-blue-200 rounded-full">
                    <Loader2 size={14} className="text-blue-600 animate-spin" />
                    <span className="text-xs text-blue-700 font-medium">
                      Actualizando cada 3s
                    </span>
                  </div>
                )}
              </div>
              <button
                onClick={() => setShowDetailModal(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
              >
                ×
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Execution summary */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="rounded-xl border border-blue-100 bg-gradient-to-br from-blue-50 to-indigo-50 p-4 shadow-sm">
                  <div className="flex items-center justify-between text-xs font-semibold text-blue-700">
                    <span>Tokens Totales</span>
                    <span className="px-2 py-0.5 rounded-full bg-white/60 text-[11px]">
                      In / Out
                    </span>
                  </div>
                  <div className="mt-1 text-2xl font-bold text-blue-900">
                    {selectedExecutionTotalTokens.toLocaleString("es-ES")}
                  </div>
                  <div className="text-[11px] text-blue-700 mt-1">
                    In: {selectedExecutionInputTokens.toLocaleString("es-ES")} · Out: {selectedExecutionOutputTokens.toLocaleString("es-ES")}
                  </div>
                </div>

                <div className="rounded-xl border border-amber-100 bg-gradient-to-br from-amber-50 to-orange-50 p-4 shadow-sm">
                  <div className="text-xs font-semibold text-amber-700">Costo USD</div>
                  <div className="mt-2 text-2xl font-bold text-amber-900">
                    ${selectedExecutionCost.toFixed(4)}
                  </div>
                  <div className="text-[11px] text-amber-700 mt-1">Incluye todos los stages</div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="text-xs font-semibold text-slate-600">Duración</div>
                  <div className="mt-2 text-2xl font-bold text-slate-900">
                    {formatDuration(selectedExecution.duration_seconds)}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    Desde {new Date(selectedExecution.created_at).toLocaleTimeString("es-ES")}
                  </div>
                </div>

                <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4 shadow-sm">
                  <div className="flex items-center justify-between text-xs font-semibold text-emerald-700">
                    <span>Stages</span>
                    <span className="px-2 py-0.5 rounded-full bg-white/70 text-[11px]">
                      {selectedExecution.status === "running" ? "En curso" : selectedExecution.status === "completed" ? "Listo" : "Pendiente"}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="text-2xl font-bold text-emerald-900">
                      {selectedExecution.completed_stages}/{selectedExecution.total_stages}
                    </div>
                    <div className="flex-1 h-2 rounded-full bg-white/70 overflow-hidden">
                      <div
                        className="h-full bg-emerald-500"
                        style={{
                          width: `${Math.min(100, Math.round((selectedExecution.completed_stages / Math.max(1, selectedExecution.total_stages)) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">Detalles rápidos</div>
                    <div className="text-xs text-slate-500">Contexto de la ejecución y API usada</div>
                  </div>
                  {selectedExecution.status === "failed" && selectedExecution.error_message && (
                    <span className="rounded-full bg-red-100 text-red-700 text-xs font-semibold px-3 py-1">
                      Error reportado
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-slate-700">
                  <div className="rounded-lg bg-white/70 border border-slate-200 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Newsletter</div>
                    <div className="font-semibold text-slate-900">
                      {selectedExecution.newsletter_config_name || "(Config eliminada)"}
                    </div>
                  </div>
                  <div className="rounded-lg bg-white/70 border border-slate-200 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Fecha</div>
                    <div className="font-semibold text-slate-900">{selectedExecution.run_date}</div>
                  </div>
                  <div className="rounded-lg bg-white/70 border border-slate-200 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">Disparo</div>
                    <div className="font-semibold text-slate-900">
                      {selectedExecution.execution_type === "manual" ? "Manual" : "Programado"}
                    </div>
                  </div>
                  <div className="rounded-lg bg-white/70 border border-slate-200 px-3 py-2">
                    <div className="text-[11px] uppercase tracking-wide text-slate-500">API Key</div>
                    <div className="font-semibold text-slate-900">
                      {selectedExecution.api_key_alias
                        ? selectedExecution.api_key_alias
                        : selectedExecution.api_key_id
                        ? `ID ${selectedExecution.api_key_id}`
                        : "No especificada"}
                    </div>
                  </div>
                  {selectedExecution.status === "failed" && selectedExecution.error_message && (
                    <div className="sm:col-span-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
                      {selectedExecution.error_message}
                    </div>
                  )}
                </div>
              </div>

              <NewsletterStageProgress stages={stageDetails} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
