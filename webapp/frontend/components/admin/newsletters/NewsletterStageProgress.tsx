"use client";

import { CheckCircle, Loader2, XCircle, Clock, Sparkles } from "lucide-react";

interface StageInfo {
  stage_number: number;
  stage_name: string;
  status: "pending" | "running" | "completed" | "failed" | "aborted";
  items_processed?: number;
  items_successful?: number;
  items_failed?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
  duration_seconds?: number | null;
  error_message?: string | null;
}

interface NewsletterStageProgressProps {
  stages: StageInfo[];
  currentStage?: number | null;
}

const statusStyles = {
  completed: {
    label: "Completado",
    badge: "bg-green-50 text-green-700 border-green-200",
    accent: "border-l-4 border-l-green-500",
    icon: <CheckCircle size={14} />,
  },
  running: {
    label: "En proceso",
    badge: "bg-blue-50 text-blue-700 border-blue-200",
    accent: "border-l-4 border-l-blue-500",
    icon: <Loader2 size={14} className="animate-spin" />,
  },
  failed: {
    label: "Error",
    badge: "bg-red-50 text-red-700 border-red-200",
    accent: "border-l-4 border-l-red-500",
    icon: <XCircle size={14} />,
  },
  aborted: {
    label: "Abortado",
    badge: "bg-gray-50 text-gray-700 border-gray-200",
    accent: "border-l-4 border-l-gray-400",
    icon: <XCircle size={14} />,
  },
  pending: {
    label: "Esperando",
    badge: "bg-slate-50 text-slate-600 border-slate-200",
    accent: "border-l-4 border-l-slate-300",
    icon: <Clock size={14} />,
  },
};

const formatDuration = (seconds: number | null | undefined) => {
  if (!seconds) return "0s";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}m ${secs}s`;
};

const formatStageNumber = (value: number) =>
  value.toString().padStart(2, "0");

export default function NewsletterStageProgress({
  stages,
}: NewsletterStageProgressProps) {
  const totalStages = Math.max(1, stages.length);
  const completed = stages.filter((stage) => stage.status === "completed").length;
  const running = stages.find((stage) => stage.status === "running");
  const progress = Math.min(100, Math.round((completed / totalStages) * 100));

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-blue-500 text-white shadow-md">
            <Sparkles size={18} />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">
              Estado de los stages
            </div>
            <div className="text-xs text-slate-500">
              Vista compacta con métricas clave
            </div>
          </div>
        </div>
        <div className="w-full sm:max-w-xs">
          <div className="flex justify-between text-[11px] text-slate-500 mb-1">
            <span>{completed} completados</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2.5 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={`h-full ${
                running
                  ? "bg-blue-600"
                  : completed === totalStages
                  ? "bg-green-600"
                  : "bg-slate-400"
              } transition-all`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {stages.map((stage) => {
          const processed =
            stage.items_processed !== undefined && stage.items_processed !== null
              ? stage.items_processed
              : (stage.items_successful ?? 0) + (stage.items_failed ?? 0);

          const style =
            statusStyles[stage.status as keyof typeof statusStyles] ||
            statusStyles.pending;

          return (
            <div
              key={stage.stage_number}
              className={`relative rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg ${style.accent}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-slate-500">
                    Stage {formatStageNumber(stage.stage_number)}
                  </div>
                  <div
                    className="text-sm font-semibold text-slate-900 leading-snug"
                    title={stage.stage_name}
                  >
                    {stage.stage_name}
                  </div>
                </div>
                <span
                  className={`inline-flex items-center gap-1 border text-[11px] font-semibold px-2.5 py-1 rounded-full ${style.badge}`}
                >
                  {style.icon}
                  {style.label}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-[12px] text-slate-600">
                {processed > 0 && (
                  <div className="flex items-center justify-between rounded-lg bg-slate-50 px-2 py-1.5">
                    <span>Procesados</span>
                    <span className="font-semibold text-slate-900">
                      {processed}
                    </span>
                  </div>
                )}

                {stage.items_successful !== undefined &&
                  stage.items_successful > 0 && (
                    <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-2 py-1.5 text-emerald-700">
                      <span>Exitosos</span>
                      <span className="font-semibold">
                        {stage.items_successful}
                      </span>
                    </div>
                  )}

                {stage.items_failed !== undefined && stage.items_failed > 0 && (
                  <div className="flex items-center justify-between rounded-lg bg-red-50 px-2 py-1.5 text-red-700">
                    <span>Fallidos</span>
                    <span className="font-semibold">{stage.items_failed}</span>
                  </div>
                )}

                {stage.duration_seconds !== undefined &&
                  stage.duration_seconds !== null && (
                    <div className="flex items-center justify-between rounded-lg bg-slate-50 px-2 py-1.5">
                      <span>Duración</span>
                      <span className="font-semibold text-slate-900">
                        {formatDuration(stage.duration_seconds)}
                      </span>
                    </div>
                  )}

                {stage.total_tokens !== undefined && (
                  <div className="flex items-center justify-between rounded-lg bg-purple-50 px-2 py-1.5 text-purple-800">
                    <span>Tokens</span>
                    <span className="font-semibold">
                      {stage.total_tokens.toLocaleString("es-ES")}
                    </span>
                  </div>
                )}

                {stage.cost_usd !== undefined && (
                  <div className="flex items-center justify-between rounded-lg bg-amber-50 px-2 py-1.5 text-amber-800">
                    <span>Costo</span>
                    <span className="font-semibold">
                      ${stage.cost_usd.toFixed(4)}
                    </span>
                  </div>
                )}
              </div>

              {stage.error_message && stage.status === "failed" && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
                  {stage.error_message}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
