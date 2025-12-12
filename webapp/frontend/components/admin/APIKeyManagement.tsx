"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { Loader2, Plus, Trash2, Edit, Eye, EyeOff, TestTube } from "lucide-react";

interface APIKey {
  id: number;
  alias: string;
  user_id: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  usage_count: number;
  notes: string | null;
  key_preview: string;
  use_as_fallback: boolean;
}

export default function APIKeyManagement() {
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingKey, setEditingKey] = useState<APIKey | null>(null);
  const [testingKeyId, setTestingKeyId] = useState<number | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    alias: "",
    api_key: "",
    notes: "",
    use_as_fallback: true,
  });

  useEffect(() => {
    loadAPIKeys();
  }, []);

  const loadAPIKeys = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get("/api-keys");
      setApiKeys(response.data.api_keys);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load API keys");
      console.error("Error loading API keys:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.post("/api-keys", formData);
      setShowCreateModal(false);
      setFormData({ alias: "", api_key: "", notes: "", use_as_fallback: true });
      loadAPIKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to create API key");
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingKey) return;

    try {
      const updateData: any = {
        alias: formData.alias,
        notes: formData.notes,
        use_as_fallback: formData.use_as_fallback,
      };

      // Only include api_key if it's been changed
      if (formData.api_key) {
        updateData.api_key = formData.api_key;
      }

      await apiClient.put(`/api-keys/${editingKey.id}`, updateData);
      setShowEditModal(false);
      setEditingKey(null);
      setFormData({ alias: "", api_key: "", notes: "", use_as_fallback: true });
      loadAPIKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to update API key");
    }
  };

  const handleDelete = async (id: number, alias: string) => {
    if (!confirm(`Are you sure you want to delete API key "${alias}"?`)) return;

    try {
      await apiClient.delete(`/api-keys/${id}`);
      loadAPIKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to delete API key");
    }
  };

  const handleTest = async (alias: string, id: number) => {
    try {
      setTestingKeyId(id);
      const response = await apiClient.post("/api-keys/test", { alias });

      if (response.data.success) {
        alert(`✅ API Key is valid!\n\n${response.data.message}`);
      } else {
        alert(`❌ API Key test failed:\n\n${response.data.message}`);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to test API key");
    } finally {
      setTestingKeyId(null);
    }
  };

  const handleToggleActive = async (key: APIKey) => {
    try {
      await apiClient.put(`/api-keys/${key.id}`, {
        is_active: !key.is_active,
      });
      loadAPIKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to toggle API key status");
    }
  };

  const openEditModal = (key: APIKey) => {
    setEditingKey(key);
    setFormData({
      alias: key.alias,
      api_key: "", // Don't pre-fill the key for security
      notes: key.notes || "",
      use_as_fallback: key.use_as_fallback,
    });
    setShowEditModal(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-blue-600" size={48} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Claves API</h2>
          <p className="text-sm text-gray-600 mt-1">
            Gestiona claves API de OpenAI encriptadas para la generación de newsletters
          </p>
        </div>
        <button
          onClick={() => {
            setFormData({ alias: "", api_key: "", notes: "", use_as_fallback: true });
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <Plus size={20} />
          Añadir Clave API
        </button>
      </div>

      {/* API Keys Table */}
      {apiKeys.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">No hay claves API configuradas aún.</p>
          <p className="text-sm text-gray-500 mt-2">
            Añade tu primera clave API de OpenAI para comenzar a generar newsletters.
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Alias
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Vista Previa
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Estado
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Uso
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Último Uso
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {apiKeys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="font-medium text-gray-900">{key.alias}</div>
                    {key.notes && (
                      <div className="text-xs text-gray-500 mt-1">{key.notes}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <code className="text-sm bg-gray-100 px-2 py-1 rounded">
                      {key.key_preview}
                    </code>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => handleToggleActive(key)}
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        key.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {key.is_active ? "Activa" : "Inactiva"}
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {key.usage_count} usos
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {key.last_used_at
                      ? new Date(key.last_used_at).toLocaleString('es-ES')
                      : "Nunca"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleTest(key.alias, key.id)}
                        disabled={testingKeyId === key.id}
                        className="text-blue-600 hover:text-blue-800 disabled:opacity-50"
                        title="Test API Key"
                      >
                        {testingKeyId === key.id ? (
                          <Loader2 size={18} className="animate-spin" />
                        ) : (
                          <TestTube size={18} />
                        )}
                      </button>
                      <button
                        onClick={() => openEditModal(key)}
                        className="text-gray-600 hover:text-gray-800"
                        title="Edit API Key"
                      >
                        <Edit size={18} />
                      </button>
                      <button
                        onClick={() => handleDelete(key.id, key.alias)}
                        className="text-red-600 hover:text-red-800"
                        title="Delete API Key"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold mb-4">Añadir Nueva Clave API</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Alias *
                </label>
                <input
                  type="text"
                  value={formData.alias}
                  onChange={(e) =>
                    setFormData({ ...formData, alias: e.target.value })
                  }
                  required
                  placeholder="ej., Clave Producción, Clave Pruebas"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Clave API de OpenAI *
                </label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) =>
                    setFormData({ ...formData, api_key: e.target.value })
                  }
                  required
                  placeholder="sk-..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Tu clave será encriptada antes de almacenarse
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notas
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) =>
                    setFormData({ ...formData, notes: e.target.value })
                  }
                  placeholder="Notas opcionales sobre esta clave..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="use_as_fallback_create"
                  checked={formData.use_as_fallback}
                  onChange={(e) =>
                    setFormData({ ...formData, use_as_fallback: e.target.checked })
                  }
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="use_as_fallback_create" className="text-sm text-gray-700">
                  Usar como fallback (si la clave principal se queda sin créditos)
                </label>
              </div>
              <div className="flex gap-3 justify-end pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Añadir Clave
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && editingKey && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold mb-4">Editar Clave API</h3>
            <form onSubmit={handleUpdate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Alias *
                </label>
                <input
                  type="text"
                  value={formData.alias}
                  onChange={(e) =>
                    setFormData({ ...formData, alias: e.target.value })
                  }
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Clave API de OpenAI
                </label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) =>
                    setFormData({ ...formData, api_key: e.target.value })
                  }
                  placeholder="Dejar vacío para mantener la clave actual"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Dejar vacío para mantener la clave existente
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notas
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) =>
                    setFormData({ ...formData, notes: e.target.value })
                  }
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="use_as_fallback_edit"
                  checked={formData.use_as_fallback}
                  onChange={(e) =>
                    setFormData({ ...formData, use_as_fallback: e.target.checked })
                  }
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="use_as_fallback_edit" className="text-sm text-gray-700">
                  Usar como fallback (si la clave principal se queda sin créditos)
                </label>
              </div>
              <div className="flex gap-3 justify-end pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowEditModal(false);
                    setEditingKey(null);
                  }}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Actualizar Clave
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
