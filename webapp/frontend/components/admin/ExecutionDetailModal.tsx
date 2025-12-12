"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api-client";

interface ExecutionDetailModalProps {
  executionId: number;
  onClose: () => void;
}

interface URLDetail {
  id: number;
  url: string;
  title: string | null;
  source: string;
  content_type: string | null;
  content_subtype: string | null;
  categoria_tematica: string | null;
  classification_method: string | null;
  rule_name: string | null;
  extracted_at: string;
  last_extracted_at: string | null;
}

interface SourceStats {
  source: string;
  total_urls: number;
  content_urls: number;
  non_content_urls: number;
  categorized_urls: number;
}

interface CategoryStats {
  categoria_tematica: string;
  url_count: number;
}

interface ExecutionDetails {
  execution: any;
  urls: URLDetail[];
  stats_by_source: SourceStats[];
  stats_by_category: CategoryStats[];
  total_urls: number;
}

export default function ExecutionDetailModal({
  executionId,
  onClose,
}: ExecutionDetailModalProps) {
  const [details, setDetails] = useState<ExecutionDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "urls" | "sources" | "categories">("overview");

  // Pagination for URLs
  const [urlPage, setUrlPage] = useState(0);
  const urlsPerPage = 20;

  const fetchDetails = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(
        `/stage-executions/${executionId}/details`
      );
      setDetails(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al cargar detalles");
    } finally {
      setLoading(false);
    }
  }, [executionId]);

  useEffect(() => {
    fetchDetails();
  }, [fetchDetails]);

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

  const statusTranslations: Record<string, string> = {
    pending: "Pendiente",
    running: "Ejecutando",
    completed: "Completado",
    failed: "Fallido",
    aborted: "Abortado",
  };

  const categoryTranslations: Record<string, string> = {
    economia: "Economía",
    politica: "Política",
    deportes: "Deportes",
    tecnologia: "Tecnología",
    cultura: "Cultura",
    internacional: "Internacional",
    nacional: "Nacional",
    opinion: "Opinión",
    sociedad: "Sociedad",
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8">
          <div className="flex items-center space-x-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="text-lg">Cargando detalles...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !details) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 max-w-md">
          <h3 className="text-lg font-semibold text-red-600 mb-4">Error</h3>
          <p className="text-gray-700 mb-4">{error || "No se encontraron detalles"}</p>
          <button
            onClick={onClose}
            className="w-full bg-gray-600 text-white py-2 px-4 rounded hover:bg-gray-700"
          >
            Cerrar
          </button>
        </div>
      </div>
    );
  }

  const { execution, urls, stats_by_source, stats_by_category, total_urls } = details;

  // Paginated URLs
  const paginatedUrls = urls.slice(
    urlPage * urlsPerPage,
    (urlPage + 1) * urlsPerPage
  );
  const totalPages = Math.ceil(urls.length / urlsPerPage);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 flex justify-between items-start">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <h2 className="text-2xl font-bold text-gray-800">
                Ejecución #{execution.id}
              </h2>
              <span
                className={`px-3 py-1 text-sm font-semibold rounded-full ${getStatusColor(
                  execution.status
                )}`}
              >
                {statusTranslations[execution.status] || execution.status}
              </span>
            </div>
            <p className="text-sm text-gray-600">
              {execution.execution_type === "manual" ? "🤚 Manual" : "⏰ Programada"} •{" "}
              {new Date(execution.created_at).toLocaleString("es-ES")}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
          >
            ×
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 px-6">
          <div className="flex space-x-6">
            <button
              onClick={() => setActiveTab("overview")}
              className={`py-3 px-4 font-medium transition-colors border-b-2 ${
                activeTab === "overview"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              📊 Resumen
            </button>
            <button
              onClick={() => setActiveTab("urls")}
              className={`py-3 px-4 font-medium transition-colors border-b-2 ${
                activeTab === "urls"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              🔗 URLs ({urls.length})
            </button>
            <button
              onClick={() => setActiveTab("sources")}
              className={`py-3 px-4 font-medium transition-colors border-b-2 ${
                activeTab === "sources"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              📰 Por Fuente ({stats_by_source.length})
            </button>
            <button
              onClick={() => setActiveTab("categories")}
              className={`py-3 px-4 font-medium transition-colors border-b-2 ${
                activeTab === "categories"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-800"
              }`}
            >
              🏷️ Por Categoría ({stats_by_category.length})
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Overview Tab */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Key Metrics */}
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div
                    className="text-sm text-blue-600 font-medium mb-1"
                    title="Total acumulado de URLs en BD para los sources de esta ejecución"
                  >
                    URLs en BD
                  </div>
                  <div className="text-3xl font-bold text-blue-700">{execution.total_items.toLocaleString('es-ES')}</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <div
                    className="text-sm text-green-600 font-medium mb-1"
                    title="URLs nuevas añadidas en esta ejecución"
                  >
                    Nuevas (+)
                  </div>
                  <div className="text-3xl font-bold text-green-700">{execution.processed_items.toLocaleString('es-ES')}</div>
                </div>
                <div className="bg-cyan-50 rounded-lg p-4">
                  <div
                    className="text-sm text-cyan-600 font-medium mb-1"
                    title="URLs existentes actualizadas en esta ejecución"
                  >
                    Actualizadas (~)
                  </div>
                  <div className="text-3xl font-bold text-cyan-700">{(execution.updated_items || 0).toLocaleString('es-ES')}</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="text-sm text-purple-600 font-medium mb-1">Tokens</div>
                  <div className="text-3xl font-bold text-purple-700">
                    {execution.total_tokens.toLocaleString("es-ES")}
                  </div>
                </div>
                <div className="bg-amber-50 rounded-lg p-4">
                  <div className="text-sm text-amber-600 font-medium mb-1">Costo</div>
                  <div className="text-3xl font-bold text-amber-700">
                    ${execution.cost_usd.toFixed(4)}
                  </div>
                </div>
              </div>

              {/* Execution Details */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold text-gray-800 mb-3">Detalles de Ejecución</h3>
                <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                  <div>
                    <span className="text-gray-500">API Key:</span>{" "}
                    <span className="font-medium text-gray-800">
                      {execution.api_key_alias || "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Duración:</span>{" "}
                    <span className="font-medium text-gray-800">
                      {execution.duration_seconds
                        ? `${Math.floor(execution.duration_seconds / 60)}m ${
                            execution.duration_seconds % 60
                          }s`
                        : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Inicio:</span>{" "}
                    <span className="font-medium text-gray-800">
                      {execution.started_at
                        ? new Date(execution.started_at).toLocaleString("es-ES")
                        : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Fin:</span>{" "}
                    <span className="font-medium text-gray-800">
                      {execution.completed_at
                        ? new Date(execution.completed_at).toLocaleString("es-ES")
                        : "N/A"}
                    </span>
                  </div>
                  {execution.parameters?.source_names && (
                    <div className="col-span-2">
                      <span className="text-gray-500">Fuentes Filtradas:</span>{" "}
                      <span className="font-medium text-gray-800">
                        {execution.parameters.source_names.join(", ")}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Top Sources Preview */}
              {stats_by_source.length > 0 && (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-800 mb-3">Top 5 Fuentes</h3>
                  <div className="space-y-2">
                    {stats_by_source.slice(0, 5).map((stat) => (
                      <div key={stat.source} className="flex justify-between items-center">
                        <span className="text-sm text-gray-700">{stat.source}</span>
                        <span className="text-sm font-medium text-gray-800">
                          {stat.total_urls} URLs
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* URLs Tab */}
          {activeTab === "urls" && (
            <div className="space-y-4">
              {urls.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  No se encontraron URLs
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    {paginatedUrls.map((url) => (
                      <div
                        key={url.id}
                        className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <a
                            href={url.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 font-medium text-sm flex-1 mr-4"
                          >
                            {url.title || url.url}
                          </a>
                          <div className="flex items-center space-x-2">
                            {url.content_type && (
                              <span
                                className={`px-2 py-0.5 text-xs rounded-full ${
                                  url.content_type === "contenido"
                                    ? "bg-green-100 text-green-800"
                                    : "bg-gray-100 text-gray-800"
                                }`}
                              >
                                {url.content_type === "contenido" ? "✓ Contenido" : "✗ No Contenido"}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center space-x-4 text-xs text-gray-600">
                          <span>📰 {url.source}</span>
                          {url.categoria_tematica && (
                            <span>
                              🏷️ {categoryTranslations[url.categoria_tematica] || url.categoria_tematica}
                            </span>
                          )}
                          {url.classification_method && (
                            <span>🔍 {url.classification_method}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex justify-center items-center space-x-2 mt-4">
                      <button
                        onClick={() => setUrlPage(Math.max(0, urlPage - 1))}
                        disabled={urlPage === 0}
                        className="px-3 py-1 border border-gray-300 rounded disabled:opacity-50"
                      >
                        ← Anterior
                      </button>
                      <span className="text-sm text-gray-600">
                        Página {urlPage + 1} de {totalPages}
                      </span>
                      <button
                        onClick={() => setUrlPage(Math.min(totalPages - 1, urlPage + 1))}
                        disabled={urlPage === totalPages - 1}
                        className="px-3 py-1 border border-gray-300 rounded disabled:opacity-50"
                      >
                        Siguiente →
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Sources Tab */}
          {activeTab === "sources" && (
            <div className="space-y-3">
              {stats_by_source.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  No hay estadísticas por fuente
                </div>
              ) : (
                stats_by_source.map((stat) => (
                  <div
                    key={stat.source}
                    className="bg-white border border-gray-200 rounded-lg p-4"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <h4 className="font-semibold text-gray-800">{stat.source}</h4>
                      <span className="text-2xl font-bold text-blue-600">
                        {stat.total_urls}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <div className="text-gray-500">Contenido</div>
                        <div className="text-lg font-semibold text-green-600">
                          {stat.content_urls}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500">No Contenido</div>
                        <div className="text-lg font-semibold text-gray-600">
                          {stat.non_content_urls}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500">Categorizadas</div>
                        <div className="text-lg font-semibold text-purple-600">
                          {stat.categorized_urls}
                        </div>
                      </div>
                    </div>
                    {/* Progress bar */}
                    <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500"
                        style={{
                          width: `${(stat.content_urls / stat.total_urls) * 100}%`,
                        }}
                      />
                    </div>
                    <div className="mt-1 text-xs text-gray-500 text-right">
                      {Math.round((stat.content_urls / stat.total_urls) * 100)}% contenido
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Categories Tab */}
          {activeTab === "categories" && (
            <div className="space-y-3">
              {stats_by_category.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  No hay estadísticas por categoría
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    {stats_by_category.map((stat) => (
                      <div
                        key={stat.categoria_tematica}
                        className="bg-white border border-gray-200 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-center">
                          <span className="font-medium text-gray-800">
                            {categoryTranslations[stat.categoria_tematica] ||
                              stat.categoria_tematica}
                          </span>
                          <span className="text-xl font-bold text-blue-600">
                            {stat.url_count}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="bg-gray-600 text-white py-2 px-6 rounded hover:bg-gray-700 font-medium"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
