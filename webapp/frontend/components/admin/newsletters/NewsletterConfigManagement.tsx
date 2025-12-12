"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { Loader2, Plus, Trash2, Edit, Power, PowerOff, ShieldCheck, Globe2 } from "lucide-react";
import { useNewsletterConfigs } from "@/contexts/NewsletterConfigsContext";

interface NewsletterConfig {
  id: number;
  name: string;
  display_name: string | null;
  description: string | null;
  source_ids: number[];
  category_ids: string[];
  articles_count: number;
  ranker_method: string;
  output_format: string;
  template_name: string;
  skip_paywall_check: boolean;
  related_window_days: number;
  is_active: boolean;
  api_key_id: number | null;
  enable_fallback: boolean;
  visibility?: "public" | "private";
  created_at: string;
  updated_at: string;
}

interface Source {
  id: number;
  name: string;
  is_active: boolean;
}

interface Category {
  id: string;
  name: string;
}

interface APIKey {
  id: number;
  alias: string;
  is_active: boolean;
}

const slugifyName = (value: string) =>
  value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

export default function NewsletterConfigManagement() {
  const { configs, loading: configsLoading, refreshConfigs } = useNewsletterConfigs();
  const [sources, setSources] = useState<Source[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingConfig, setEditingConfig] = useState<NewsletterConfig | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    display_name: "",
    description: "",
    visibility: "private" as "public" | "private",
    source_ids: [] as number[],
    category_ids: [] as string[],
    articles_count: 20,
    ranker_method: "level_scoring",
    output_format: "markdown",
    template_name: "default",
    skip_paywall_check: false,
    related_window_days: 365,
    is_active: true,
    api_key_id: null as number | null,
    enable_fallback: true,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [sourcesRes, categoriesRes, apiKeysRes] = await Promise.all([
        apiClient.get("/sources"),
        apiClient.get("/categories"),
        apiClient.get("/api-keys"),
      ]);
      setSources(sourcesRes.data || []);
      setCategories(categoriesRes.data || []);
      setApiKeys(apiKeysRes.data?.api_keys || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load data");
      console.error("Error loading data:", err);
      // Set empty arrays on error to prevent crashes
      setSources([]);
      setCategories([]);
      setApiKeys([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const generatedName =
        formData.name || slugifyName(formData.display_name) || `newsletter_${Date.now()}`;
      const normalizedDisplay = formData.display_name.trim().toLowerCase();
      const hasDisplayConflict =
        normalizedDisplay &&
        configs.some(
          (c) => (c.display_name || "").trim().toLowerCase() === normalizedDisplay
        );
      const hasSlugConflict = configs.some((c) => c.name === generatedName);

      if (hasDisplayConflict || hasSlugConflict) {
        setFormError(
          hasDisplayConflict
            ? "Ya existe una newsletter con ese nombre visible. Usa uno distinto."
            : "El ID generado ya existe. Ajusta el nombre visible para hacerlo único."
        );
        return;
      }

      await apiClient.post("/newsletter-configs", {
        ...formData,
        name: generatedName,
      });
      setShowCreateModal(false);
      resetForm();
      setFormError(null);
      await refreshConfigs();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to create newsletter config");
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingConfig) return;

    try {
      const normalizedDisplay = formData.display_name.trim().toLowerCase();
      const hasDisplayConflict =
        normalizedDisplay &&
        configs.some(
          (c) =>
            c.id !== editingConfig.id &&
            (c.display_name || "").trim().toLowerCase() === normalizedDisplay
        );
      if (hasDisplayConflict) {
        setFormError("Ya existe una newsletter con ese nombre visible. Usa uno distinto.");
        return;
      }

      const { name, ...updateData } = formData; // Exclude name from update
      await apiClient.put(`/newsletter-configs/${editingConfig.id}`, updateData);
      setShowEditModal(false);
      setEditingConfig(null);
      resetForm();
      setFormError(null);
      await refreshConfigs();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to update newsletter config");
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`¿Seguro que quieres eliminar la newsletter "${name}"?`)) return;

    try {
      await apiClient.delete(`/newsletter-configs/${id}`);
      await refreshConfigs();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to delete newsletter config");
    }
  };

  const handleToggleActive = async (config: NewsletterConfig) => {
    try {
      await apiClient.put(`/newsletter-configs/${config.id}`, {
        is_active: !config.is_active,
      });
      await refreshConfigs();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to toggle newsletter status");
    }
  };

  const openEditModal = (config: NewsletterConfig) => {
    setEditingConfig(config);
    setFormError(null);
    setFormData({
      name: config.name,
      display_name: config.display_name || "",
      description: config.description || "",
      visibility: (config.visibility as "public" | "private") || "private",
      source_ids: config.source_ids,
      category_ids: config.category_ids,
      articles_count: config.articles_count,
      ranker_method: config.ranker_method,
      output_format: config.output_format,
      api_key_id: config.api_key_id,
      enable_fallback: config.enable_fallback,
      template_name: config.template_name,
      skip_paywall_check: config.skip_paywall_check,
      related_window_days: config.related_window_days,
      is_active: config.is_active,
    });
    setShowEditModal(true);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      display_name: "",
      description: "",
      visibility: "private",
      source_ids: [],
      category_ids: [],
      articles_count: 20,
      ranker_method: "level_scoring",
      output_format: "markdown",
      template_name: "default",
      skip_paywall_check: false,
      related_window_days: 365,
      is_active: true,
      api_key_id: null,
      enable_fallback: true,
    });
  };

  const toggleSourceSelection = (sourceId: number) => {
    setFormData((prev) => ({
      ...prev,
      source_ids: prev.source_ids.includes(sourceId)
        ? prev.source_ids.filter((id) => id !== sourceId)
        : [...prev.source_ids, sourceId],
    }));
  };

  const toggleCategorySelection = (categoryId: string) => {
    setFormData((prev) => ({
      ...prev,
      category_ids: prev.category_ids.includes(categoryId)
        ? prev.category_ids.filter((id) => id !== categoryId)
        : [...prev.category_ids, categoryId],
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-blue-600" size={48} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">
            Configuraciones de Newsletters
          </h2>
          <p className="text-gray-600 mt-1">
            Gestiona las newsletters y su configuración
          </p>
        </div>
        <button
          onClick={() => {
            setFormError(null);
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus size={20} />
          Nueva Newsletter
        </button>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Nombre
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Fuentes
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Categorías
              </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Artículos
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Visibilidad
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Estado
            </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {configs.map((config) => (
              <tr key={config.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div>
                    <div className="text-sm font-medium text-gray-900">
                      {config.display_name || config.name}
                    </div>
                    <div className="text-sm text-gray-500">{config.name}</div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm text-gray-900">
                    {config.source_ids.length} fuentes
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {config.category_ids.slice(0, 3).map((catId) => (
                      <span
                        key={catId}
                        className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded"
                      >
                        {catId}
                      </span>
                    ))}
                    {config.category_ids.length > 3 && (
                      <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                        +{config.category_ids.length - 3}
                      </span>
                    )}
                  </div>
                </td>
            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
              {config.articles_count}
            </td>
            <td className="px-6 py-4 whitespace-nowrap">
              {config.visibility === "private" ? (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold text-orange-700 bg-orange-50 ring-1 ring-orange-200">
                  <ShieldCheck className="w-4 h-4" />
                  Privada
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold text-indigo-700 bg-indigo-50 ring-1 ring-indigo-200">
                  <Globe2 className="w-4 h-4" />
                  Pública
                </span>
              )}
            </td>
            <td className="px-6 py-4 whitespace-nowrap">
              <button
                onClick={() => handleToggleActive(config)}
                className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
                  config.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {config.is_active ? (
                      <>
                        <Power size={14} />
                        Activa
                      </>
                    ) : (
                      <>
                        <PowerOff size={14} />
                        Inactiva
                      </>
                    )}
                  </button>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => openEditModal(config)}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      <Edit size={18} />
                    </button>
                    <button
                      onClick={() => handleDelete(config.id, config.name)}
                      className="text-red-600 hover:text-red-800"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {configs.length === 0 && !loading && (
          <div className="text-center py-12 text-gray-500">
            No hay newsletters configuradas. Crea una para empezar.
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <FormModal
          title="Crear Nueva Newsletter"
          formData={formData}
          setFormData={setFormData}
          sources={sources}
          categories={categories}
          apiKeys={apiKeys}
          onSubmit={handleCreate}
          formError={formError}
          setFormError={setFormError}
          onClose={() => {
            setShowCreateModal(false);
            resetForm();
            setFormError(null);
          }}
          toggleSourceSelection={toggleSourceSelection}
          toggleCategorySelection={toggleCategorySelection}
          isEdit={false}
        />
      )}

      {/* Edit Modal */}
      {showEditModal && editingConfig && (
        <FormModal
          title={`Editar Newsletter: ${editingConfig.name}`}
          formData={formData}
          setFormData={setFormData}
          sources={sources}
          categories={categories}
          apiKeys={apiKeys}
          onSubmit={handleUpdate}
          formError={formError}
          setFormError={setFormError}
          onClose={() => {
            setShowEditModal(false);
            setEditingConfig(null);
            resetForm();
            setFormError(null);
          }}
          toggleSourceSelection={toggleSourceSelection}
          toggleCategorySelection={toggleCategorySelection}
          isEdit={true}
        />
      )}
    </div>
  );
}

// Form Modal Component
interface FormModalProps {
  title: string;
  formData: any;
  setFormData: React.Dispatch<React.SetStateAction<any>>;
  sources: Source[];
  categories: Category[];
  apiKeys: APIKey[];
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
  formError: string | null;
  setFormError: (value: string | null) => void;
  toggleSourceSelection: (id: number) => void;
  toggleCategorySelection: (id: string) => void;
  isEdit: boolean;
}

function FormModal({
  title,
  formData,
  setFormData,
  sources,
  categories,
  apiKeys,
  onSubmit,
  onClose,
  formError,
  setFormError,
  toggleSourceSelection,
  toggleCategorySelection,
  isEdit,
}: FormModalProps) {
  // Ensure apiKeys is always an array
  const safeApiKeys = Array.isArray(apiKeys) ? apiKeys : [];

  const handleDisplayNameChange = (value: string) => {
    setFormError(null);
    if (isEdit) {
      setFormData({ ...formData, display_name: value });
      return;
    }
    const slug = slugifyName(value);
    setFormData((prev: any) => ({
      ...prev,
      display_name: value,
      name: slug || prev.name,
    }));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <h3 className="text-xl font-semibold text-gray-900">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl font-bold"
          >
            ×
          </button>
        </div>

        <form onSubmit={onSubmit} className="p-6 space-y-6">
          {formError && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              {formError}
            </div>
          )}

          {/* Basic Info */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {isEdit && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  ID interno
                </label>
                <input
                  type="text"
                  disabled
                  value={formData.name}
                  className="w-full px-3 py-2 border rounded-lg bg-gray-100 cursor-not-allowed"
                  placeholder="economia_diaria"
                />
              </div>
            )}

            <div className={isEdit ? "" : "md:col-span-2"}>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nombre Visible
              </label>
              <input
                type="text"
                value={formData.display_name}
                onChange={(e) => handleDisplayNameChange(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Newsletter de Economía"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Descripción
            </label>
            <textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              rows={3}
              className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Newsletter diaria con las últimas noticias de economía..."
            />
          </div>

          {/* Visibility */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Visibilidad
            </label>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="visibility"
                  value="private"
                  checked={formData.visibility === "private"}
                  onChange={() => setFormData({ ...formData, visibility: "private" })}
                  className="w-4 h-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Privada (default)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="visibility"
                  value="public"
                  checked={formData.visibility === "public"}
                  onChange={() => setFormData({ ...formData, visibility: "public" })}
                  className="w-4 h-4 text-blue-600"
                />
                <span className="text-sm text-gray-700">Pública</span>
              </label>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Las nuevas newsletters son privadas por defecto; puedes cambiarlas a públicas o volverlas privadas luego.
            </p>
          </div>

          {/* Sources Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Fuentes de Noticias
            </label>
            <div className="border rounded-lg p-4 max-h-48 overflow-y-auto">
              <div className="grid grid-cols-2 gap-2">
                {sources.map((source) => (
                  <label
                    key={source.id}
                    className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded"
                  >
                    <input
                      type="checkbox"
                      checked={formData.source_ids.includes(source.id)}
                      onChange={() => toggleSourceSelection(source.id)}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{source.name}</span>
                  </label>
                ))}
              </div>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {formData.source_ids.length} fuentes seleccionadas
            </p>
          </div>

          {/* Categories Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Categorías
            </label>
            <div className="border rounded-lg p-4 max-h-48 overflow-y-auto">
              <div className="grid grid-cols-3 gap-2">
                {categories.map((category) => (
                  <label
                    key={category.id}
                    className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded"
                  >
                    <input
                      type="checkbox"
                      checked={formData.category_ids.includes(category.id)}
                      onChange={() => toggleCategorySelection(category.id)}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{category.name}</span>
                  </label>
                ))}
              </div>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {formData.category_ids.length} categorías seleccionadas
            </p>
          </div>

          {/* Configuration */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Cantidad de Artículos
              </label>
              <input
                type="number"
                required
                min={5}
                max={100}
                value={formData.articles_count}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    articles_count: parseInt(e.target.value),
                  })
                }
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ventana de Artículos Relacionados (días)
              </label>
              <input
                type="number"
                required
                min={0}
                value={formData.related_window_days}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    related_window_days: parseInt(e.target.value),
                  })
                }
                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* API Key Selection */}
          <div className="border-t pt-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3">🔑 Configuración de API Key</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API Key <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.api_key_id || ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      api_key_id: e.target.value ? parseInt(e.target.value) : null,
                    })
                  }
                  required
                  className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Selecciona una API Key</option>
                  {safeApiKeys.filter(k => k.is_active).map((key) => (
                    <option key={key.id} value={key.id}>
                      {key.alias}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Obligatorio: Selecciona la API key principal para esta newsletter
                </p>
              </div>

              <div className="flex items-end">
                <label className="flex items-center gap-2 cursor-pointer mb-2">
                  <input
                    type="checkbox"
                    checked={formData.enable_fallback}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        enable_fallback: e.target.checked,
                      })
                    }
                    disabled={!formData.api_key_id}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 disabled:opacity-50"
                  />
                  <div>
                    <span className="text-sm text-gray-700">Habilitar fallback automático</span>
                    <p className="text-xs text-gray-500">
                      Si falla, usar automáticamente tus otras API keys activas
                    </p>
                  </div>
                </label>
              </div>
            </div>
            {safeApiKeys.filter(k => k.is_active).length === 0 && (
              <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  ⚠️ No tienes API keys activas. Debes crear al menos una en la pestaña &quot;API Keys&quot; antes de crear newsletters.
                </p>
              </div>
            )}
          </div>

          {/* Checkboxes */}
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.skip_paywall_check}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    skip_paywall_check: e.target.checked,
                  })
                }
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">
                Omitir verificación de paywall
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) =>
                  setFormData({ ...formData, is_active: e.target.checked })
                }
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Activa</span>
            </label>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              {isEdit ? "Actualizar" : "Crear"} Newsletter
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
