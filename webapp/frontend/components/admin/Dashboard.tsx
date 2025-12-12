"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api-client";

// ============================================================================
// INTERFACES
// ============================================================================

interface ExecutionHistoryResponse {
  id: number;
  schedule_id: number | null;
  schedule_name: string | null;
  execution_type: string;
  stage_name: string;
  status: string;
  api_key_id: number | null;
  api_key_alias: string | null;
  parameters: any | null;
  celery_task_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_items: number;
  processed_items: number;
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

interface DashboardData {
  system_status: {
    has_running_execution: boolean;
    last_execution: ExecutionHistoryResponse | null;
  };
  recent_executions: ExecutionHistoryResponse[];
  execution_stats: {
    total_executions: number;
    completed: number;
    failed: number;
    running: number;
    pending: number;
    success_rate: number;
    total_cost_usd: number;
    total_tokens: number;
  };
  resource_counts: {
    total_users: number;
    active_users: number;
    total_sources: number;
    active_sources: number;
    active_schedules: number;
    total_api_keys: number;
  };
  cost_by_stage: Array<{
    stage_name: string;
    total_cost_usd: number;
    total_tokens: number;
    executions: number;
    avg_cost_per_execution: number;
  }>;
}

interface NewsletterExecution {
  id: number;
  newsletter_config_name: string;
  status: string;
  execution_type: string;
  run_date: string;
  total_stages: number;
  completed_stages: number;
  failed_stages: number;
  total_urls_processed: number;
  total_urls_ranked: number;
  total_urls_with_content: number;
  newsletter_generated: boolean;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  schedule_id?: number | null;
}

type NormalizedStageCost = DashboardData['cost_by_stage'][number];

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

const STAGE_ALIASES: Record<string, string> = {
  '01_extract_urls': 'stage_01',
  'stage_01': 'stage_01',
  'extract_urls': 'stage_01',
  'stage1': 'stage_01',
  '02_filter': 'stage_02',
  'stage_02': 'stage_02',
  '03_ranker': 'stage_03',
  'stage_03': 'stage_03',
  '04_extract_content': 'stage_04',
  'stage_04': 'stage_04',
  '05_generate': 'stage_05',
  'stage_05': 'stage_05',
};

const STAGE_LABELS: Record<string, string> = {
  'stage_01': '📥 Stage 01 - URL Scraping',
  '01_extract_urls': '📥 Stage 01 - URL Scraping',
  'stage_02': '🔍 Stage 02 - Filtrado',
  'stage_03': '📊 Stage 03 - Ranking',
  'stage_04': '📰 Stage 04 - Contenido',
  'stage_05': '✍️ Stage 05 - Newsletter',
};

function normalizeCostByStage(costByStage: DashboardData['cost_by_stage']): NormalizedStageCost[] {
  const aggregated: Record<string, NormalizedStageCost> = {};

  costByStage.forEach((stage) => {
    const canonical = STAGE_ALIASES[stage.stage_name] || stage.stage_name;
    if (!aggregated[canonical]) {
      aggregated[canonical] = { ...stage, stage_name: canonical };
      return;
    }

    aggregated[canonical] = {
      stage_name: canonical,
      total_cost_usd: aggregated[canonical].total_cost_usd + stage.total_cost_usd,
      total_tokens: aggregated[canonical].total_tokens + stage.total_tokens,
      executions: aggregated[canonical].executions + stage.executions,
      avg_cost_per_execution: 0, // recalculated below
    };
  });

  return Object.values(aggregated)
    .map((stage) => ({
      ...stage,
      avg_cost_per_execution: stage.executions > 0 ? stage.total_cost_usd / stage.executions : 0,
    }))
    .sort((a, b) => b.total_cost_usd - a.total_cost_usd);
}

// ============================================================================
// SUBCOMPONENTS
// ============================================================================

function SystemStatusCard({ hasRunning, lastExecution }: {
  hasRunning: boolean;
  lastExecution: ExecutionHistoryResponse | null;
}) {
  const statusColor = hasRunning ? 'blue' : 'green';
  const statusText = hasRunning ? 'Ejecución en Curso' : 'Sistema Disponible';
  const statusIcon = hasRunning ? '⚙️' : '✅';

  return (
    <div className={`bg-white rounded-lg shadow-md p-6 border-l-4 ${hasRunning ? 'border-blue-500' : 'border-green-500'}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-800">Estado del Sistema</h3>
        <div className="flex items-center space-x-2">
          {hasRunning && (
            <>
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
              </span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center space-x-4">
        <div className="text-5xl">{statusIcon}</div>
        <div className="flex-1">
          <p className={`text-2xl font-bold ${hasRunning ? 'text-blue-600' : 'text-green-600'}`}>
            {statusText}
          </p>
          {lastExecution && (
            <div className="mt-2 text-sm text-gray-600">
              <p>Última ejecución: <span className="font-medium">#{lastExecution.id}</span></p>
              <p>Estado: <span className={`font-medium ${lastExecution.status === 'completed' ? 'text-green-600' : lastExecution.status === 'failed' ? 'text-red-600' : 'text-blue-600'}`}>
                {lastExecution.status === 'completed' ? 'Completada' :
                 lastExecution.status === 'failed' ? 'Fallida' :
                 lastExecution.status === 'running' ? 'Ejecutando' : 'Pendiente'}
              </span></p>
              {lastExecution.started_at && (
                <p>Inicio: {new Date(lastExecution.started_at).toLocaleString('es-ES')}</p>
              )}
              {lastExecution.duration_seconds !== null && (
                <p>Duración: {formatDuration(lastExecution.duration_seconds)}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, icon, color }: {
  title: string;
  value: string | number;
  icon: string;
  color: 'green' | 'blue' | 'purple' | 'red' | 'gray';
}) {
  const colorClasses = {
    green: 'bg-green-50 border-green-200 text-green-600',
    blue: 'bg-blue-50 border-blue-200 text-blue-600',
    purple: 'bg-purple-50 border-purple-200 text-purple-600',
    red: 'bg-red-50 border-red-200 text-red-600',
    gray: 'bg-gray-50 border-gray-200 text-gray-600',
  };

  return (
    <div className={`rounded-lg shadow p-4 border-2 ${colorClasses[color]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <h4 className="text-sm font-medium text-gray-600">{title}</h4>
      </div>
      <p className="text-2xl font-bold text-gray-800">{value}</p>
    </div>
  );
}

function ExecutionStatsCard({ stats }: { stats: DashboardData['execution_stats'] }) {
  const total = stats.total_executions;
  const completedPct = total > 0 ? (stats.completed / total * 100).toFixed(1) : 0;
  const failedPct = total > 0 ? (stats.failed / total * 100).toFixed(1) : 0;
  const runningPct = total > 0 ? (stats.running / total * 100).toFixed(1) : 0;
  const pendingPct = total > 0 ? (stats.pending / total * 100).toFixed(1) : 0;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">Estadísticas de Ejecuciones</h3>

      <div className="space-y-3">
        {/* Completed */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">✅ Completadas</span>
            <span className="font-medium">{stats.completed} ({completedPct}%)</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-green-500 h-2 rounded-full" style={{ width: `${completedPct}%` }}></div>
          </div>
        </div>

        {/* Failed */}
        {stats.failed > 0 && (
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">❌ Fallidas</span>
              <span className="font-medium">{stats.failed} ({failedPct}%)</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-red-500 h-2 rounded-full" style={{ width: `${failedPct}%` }}></div>
            </div>
          </div>
        )}

        {/* Running */}
        {stats.running > 0 && (
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">⚙️ Ejecutando</span>
              <span className="font-medium">{stats.running} ({runningPct}%)</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${runningPct}%` }}></div>
            </div>
          </div>
        )}

        {/* Pending */}
        {stats.pending > 0 && (
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">⏳ Pendientes</span>
              <span className="font-medium">{stats.pending} ({pendingPct}%)</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-yellow-500 h-2 rounded-full" style={{ width: `${pendingPct}%` }}></div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-600">Total:</span>
            <span className="font-bold ml-2">{stats.total_executions}</span>
          </div>
          <div>
            <span className="text-gray-600">Tasa de éxito:</span>
            <span className="font-bold ml-2 text-green-600">{stats.success_rate}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ResourceCard({ title, active, total, icon }: {
  title: string;
  active: number;
  total: number;
  icon: string;
}) {
  return (
    <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <h4 className="text-sm font-medium text-gray-600">{title}</h4>
      </div>
      <div className="text-center">
        <p className="text-3xl font-bold text-gray-800">{active}</p>
        {active !== total && (
          <p className="text-xs text-gray-500 mt-1">de {total} totales</p>
        )}
      </div>
    </div>
  );
}

function CostByStageCard({ costByStage }: { costByStage: NormalizedStageCost[] }) {
  const totalCost = costByStage.reduce((sum, stage) => sum + stage.total_cost_usd, 0);

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">💰 Costos por Stage</h3>

      {costByStage.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">
          No hay datos de costos disponibles
        </p>
      ) : (
        <div className="space-y-3">
          {costByStage.map((stage, index) => {
            const percentage = totalCost > 0 ? (stage.total_cost_usd / totalCost * 100) : 0;
            return (
              <div key={index} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {STAGE_LABELS[stage.stage_name] || `📌 ${stage.stage_name}`}
                  </span>
                  <span className="text-sm font-bold text-blue-600">
                    ${stage.total_cost_usd.toFixed(4)}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${percentage}%` }}
                  ></div>
                </div>

                {/* Stats row */}
                <div className="flex justify-between text-xs text-gray-500">
                  <span>
                    {stage.executions} ejecución{stage.executions !== 1 ? 'es' : ''}
                  </span>
                  <span>
                    {stage.total_tokens.toLocaleString('es-ES')} tokens
                  </span>
                  <span>
                    Promedio: ${stage.avg_cost_per_execution.toFixed(4)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Total footer */}
      {costByStage.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-gray-700">Total</span>
            <span className="text-lg font-bold text-blue-600">
              ${totalCost.toFixed(4)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function RecentExecutionsTable({ executions, newsletterExecutions }: {
  executions: ExecutionHistoryResponse[];
  newsletterExecutions: NewsletterExecution[];
}) {
  const getStatusBadge = (status: string) => {
    const badges: Record<string, { label: string; color: string }> = {
      'completed': { label: 'Completado', color: 'bg-green-100 text-green-800' },
      'failed': { label: 'Fallido', color: 'bg-red-100 text-red-800' },
      'running': { label: 'Ejecutando', color: 'bg-blue-100 text-blue-800' },
      'pending': { label: 'Pendiente', color: 'bg-yellow-100 text-yellow-800' },
    };
    const badge = badges[status] || { label: status, color: 'bg-gray-100 text-gray-800' };
    return (
      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${badge.color}`}>
        {badge.label}
      </span>
    );
  };

  const combinedExecutions = [
    ...executions.map((exec) => ({
      type: 'stage' as const,
      id: exec.id,
      status: exec.status,
      execution_type: exec.execution_type,
      schedule_name: exec.schedule_name,
      started_at: exec.started_at,
      created_at: exec.created_at,
      duration_seconds: exec.duration_seconds,
      total_items: exec.total_items,
      processed_items: exec.processed_items,
      cost_usd: exec.cost_usd,
    })),
    ...newsletterExecutions.map((exec) => ({
      type: 'newsletter' as const,
      id: exec.id,
      status: exec.status,
      execution_type: exec.execution_type === 'scheduled' ? 'scheduled' : 'manual',
      schedule_name: exec.execution_type === 'scheduled' ? 'Newsletter Programada' : null,
      started_at: exec.started_at || exec.created_at,
      created_at: exec.created_at,
      duration_seconds: exec.duration_seconds,
      total_items: exec.total_urls_processed,
      processed_items: exec.total_urls_with_content,
      cost_usd: exec.total_cost_usd,
      newsletter_config_name: exec.newsletter_config_name,
      run_date: exec.run_date,
    })),
  ].sort((a, b) => {
    const timeA = new Date(a.started_at || a.created_at).getTime();
    const timeB = new Date(b.started_at || b.created_at).getTime();
    return timeB - timeA;
  }).slice(0, 10);

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-lg font-bold text-gray-800">Últimas Ejecuciones</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duración</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">URLs</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Costo</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {combinedExecutions.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-gray-500">
                  No hay ejecuciones recientes
                </td>
              </tr>
            ) : (
              combinedExecutions.map((exec) => (
                <tr key={`${exec.type}-${exec.id}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-mono text-gray-900 flex items-center gap-2">
                    <span>{exec.type === 'newsletter' ? '📧' : '🔄'}</span>
                    <span>#{exec.id}</span>
                  </td>
                  <td className="px-4 py-3">{getStatusBadge(exec.status)}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {exec.type === 'newsletter'
                      ? `${exec.execution_type === 'manual' ? '✋ Newsletter Manual' : '⏰ Newsletter Programada'}${exec.newsletter_config_name ? ` • ${exec.newsletter_config_name}` : ''}`
                      : exec.execution_type === 'manual'
                        ? '✋ Scraping Manual'
                        : `⏰ ${exec.schedule_name || 'Programada'}`
                    }
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {exec.started_at ? new Date(exec.started_at).toLocaleString('es-ES', {
                      day: '2-digit',
                      month: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    }) : new Date(exec.created_at).toLocaleString('es-ES', {
                      day: '2-digit',
                      month: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {exec.duration_seconds !== null ? formatDuration(exec.duration_seconds) : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {exec.total_items > 0 ? (
                      <span>
                        {exec.total_items}
                        {exec.processed_items > 0 && (
                          <span className="text-green-600 ml-1">
                            {exec.type === 'newsletter' ? `(${exec.processed_items} con contenido)` : `(${exec.processed_items} nuevas)`}
                          </span>
                        )}
                        {exec.type === 'newsletter' && (
                          <span className="text-indigo-600 ml-1">
                            {exec.run_date ? `• ${new Date(exec.run_date).toLocaleDateString('es-ES')}` : ''}
                          </span>
                        )}
                      </span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {exec.status === 'completed' ? `$${(exec.cost_usd || 0).toFixed(4)}` : '-'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN DASHBOARD COMPONENT
// ============================================================================

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [period, setPeriod] = useState<'7d' | '30d' | 'month' | 'all'>('all');
  const [newsletterExecutions, setNewsletterExecutions] = useState<NewsletterExecution[]>([]);

  const fetchDashboardData = useCallback(async (showSpinner = false) => {
    try {
      if (showSpinner) {
        setLoading(true);
      }
      const [dashboardRes, newsletterRes] = await Promise.allSettled([
        apiClient.get('/stage-executions/dashboard', { params: { period } }),
        apiClient.get('/newsletter-executions', { params: { limit: 5 } }),
      ]);

      if (dashboardRes.status === 'fulfilled') {
        const normalizedCost = normalizeCostByStage(dashboardRes.value.data.cost_by_stage || []);
        setData({ ...dashboardRes.value.data, cost_by_stage: normalizedCost });
        setError('');
      } else {
        throw dashboardRes.reason;
      }

      if (newsletterRes.status === 'fulfilled') {
        setNewsletterExecutions(newsletterRes.value.data || []);
      } else {
        setNewsletterExecutions([]);
        console.warn('No se pudieron cargar las ejecuciones de newsletters:', newsletterRes.reason);
      }
    } catch (err: any) {
      console.error('Failed to fetch dashboard data:', err);
      setError(err.response?.data?.detail || 'Error al cargar el dashboard');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchDashboardData(true);

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => fetchDashboardData(false), 30000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]); // Re-fetch when period changes

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Cargando dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        <p className="font-bold">Error</p>
        <p>{error}</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Period Selector */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700">Período de Análisis</h3>
          <div className="flex space-x-2">
            <button
              onClick={() => setPeriod('7d')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                period === '7d'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Últimos 7 días
            </button>
            <button
              onClick={() => setPeriod('30d')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                period === '30d'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Últimos 30 días
            </button>
            <button
              onClick={() => setPeriod('month')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                period === 'month'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Este Mes
            </button>
            <button
              onClick={() => setPeriod('all')}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                period === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Todo el Historial
            </button>
          </div>
        </div>
      </div>

      {/* System Status */}
      <SystemStatusCard
        hasRunning={data.system_status.has_running_execution}
        lastExecution={data.system_status.last_execution}
      />

      {/* Quick Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Tasa de Éxito"
          value={`${data.execution_stats.success_rate.toFixed(1)}%`}
          icon="✅"
          color="green"
        />
        <MetricCard
          title="Costo Total (USD)"
          value={`$${data.execution_stats.total_cost_usd.toFixed(4)}`}
          icon="💰"
          color="blue"
        />
        <MetricCard
          title="Total Tokens"
          value={data.execution_stats.total_tokens.toLocaleString('es-ES')}
          icon="🔤"
          color="purple"
        />
        <MetricCard
          title="Ejecuciones Fallidas"
          value={data.execution_stats.failed}
          icon="⚠️"
          color={data.execution_stats.failed > 0 ? "red" : "gray"}
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Execution Stats */}
        <ExecutionStatsCard stats={data.execution_stats} />

        {/* Cost by Stage Breakdown */}
        <CostByStageCard costByStage={data.cost_by_stage} />
      </div>

      {/* Resource Counts Grid */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-gray-800">Recursos del Sistema</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <ResourceCard
            title="Usuarios"
            active={data.resource_counts.active_users}
            total={data.resource_counts.total_users}
            icon="👥"
          />
          <ResourceCard
            title="Fuentes"
            active={data.resource_counts.active_sources}
            total={data.resource_counts.total_sources}
            icon="📰"
          />
          <ResourceCard
            title="Programaciones"
            active={data.resource_counts.active_schedules}
            total={data.resource_counts.active_schedules}
            icon="⏰"
          />
          <ResourceCard
            title="API Keys"
            active={data.resource_counts.total_api_keys}
            total={data.resource_counts.total_api_keys}
            icon="🔑"
          />
        </div>
      </div>

      {/* Recent Executions Table */}
      <RecentExecutionsTable
        executions={data.recent_executions}
        newsletterExecutions={newsletterExecutions}
      />
    </div>
  );
}
