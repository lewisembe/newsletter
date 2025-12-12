'use client';

import { useState, useEffect, useCallback } from 'react';
import { categoryApi } from '@/lib/api-client';

interface Category {
  id: string;
  name: string;
  description: string;
  consolidates: string[];
  examples: string[];
  url_count: number;
  created_at: string;
  updated_at: string;
}

interface ReclassificationJob {
  id: number;
  status: string;
  total_urls: number;
  processed_urls: number;
  failed_urls: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export default function CategoriesManagement() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [reclassificationJob, setReclassificationJob] = useState<ReclassificationJob | null>(null);
  const [showReclassifyPrompt, setShowReclassifyPrompt] = useState(false);
  const [modifiedCategoryId, setModifiedCategoryId] = useState<string | null>(null);

  const fetchCategories = useCallback(async () => {
    try {
      const response = await categoryApi.getAll();
      setCategories(response.data);
    } catch (err: any) {
      setError('Error al cargar categorías');
    } finally {
      setLoading(false);
    }
  }, []);

  const checkReclassificationStatus = useCallback(async (jobId: number) => {
    try {
      const response = await categoryApi.getReclassificationJob(jobId);
      setReclassificationJob(response.data);

      if (response.data.status === 'completed' || response.data.status === 'failed') {
        await fetchCategories();
      }
    } catch (err: any) {
      console.error('Error checking reclassification status:', err);
    }
  }, [fetchCategories]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  useEffect(() => {
    if (reclassificationJob && reclassificationJob.status === 'running') {
      const interval = setInterval(() => {
        checkReclassificationStatus(reclassificationJob.id);
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [checkReclassificationStatus, reclassificationJob]);

  const handleCreate = async (formData: {
    id: string;
    name: string;
    description: string;
    consolidates: string[];
    examples: string[];
  }) => {
    try {
      await categoryApi.create(formData);
      await fetchCategories();
      setShowCreateModal(false);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al crear categoría');
    }
  };

  const handleUpdate = async (categoryId: string, updates: {
    name?: string;
    description?: string;
    consolidates?: string[];
    examples?: string[];
  }) => {
    try {
      await categoryApi.update(categoryId, updates);
      await fetchCategories();
      setEditingCategory(null);
      setModifiedCategoryId(categoryId);
      setShowReclassifyPrompt(true);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al actualizar categoría');
    }
  };

  const handleDelete = async (categoryId: string, categoryName: string) => {
    if (categoryId === 'otros') {
      alert('No se puede eliminar la categoría "otros" (categoría de respaldo)');
      return;
    }

    if (!confirm(`¿Estás seguro de que quieres eliminar la categoría "${categoryName}"?\nLas URLs de esta categoría quedarán sin clasificar.`)) {
      return;
    }

    try {
      await categoryApi.delete(categoryId);
      await fetchCategories();
      setModifiedCategoryId(categoryId);
      setShowReclassifyPrompt(true);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al eliminar categoría');
    }
  };

  const handleReclassify = async (categoryIds: string[]) => {
    try {
      const response = await categoryApi.reclassify(categoryIds);
      setReclassificationJob(response.data);
      setShowReclassifyPrompt(false);
      setModifiedCategoryId(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al iniciar reclasificación');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8">Cargando categorías...</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
        >
          Nueva Categoría
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Reclassification Status */}
      {reclassificationJob && (
        <div className="mb-6 rounded-md bg-blue-50 p-4">
          <h3 className="text-sm font-medium text-blue-800 mb-2">
            Estado de Reclasificación
          </h3>
          <div className="text-sm text-blue-700">
            <p><strong>Estado:</strong> {reclassificationJob.status}</p>
            <p><strong>URLs procesadas:</strong> {reclassificationJob.processed_urls} / {reclassificationJob.total_urls}</p>
            {reclassificationJob.status === 'running' && (
              <div className="mt-2 w-full bg-blue-200 rounded-full h-2.5">
                <div
                  className="bg-blue-600 h-2.5 rounded-full transition-all"
                  style={{
                    width: `${(reclassificationJob.processed_urls / reclassificationJob.total_urls) * 100}%`
                  }}
                ></div>
              </div>
            )}
            {reclassificationJob.error_message && (
              <p className="mt-2 text-red-600"><strong>Error:</strong> {reclassificationJob.error_message}</p>
            )}
          </div>
        </div>
      )}

      {/* Reclassify Prompt */}
      {showReclassifyPrompt && (
        <div className="mb-6 rounded-md bg-yellow-50 p-4 border border-yellow-200">
          <h3 className="text-sm font-medium text-yellow-800 mb-2">
            ¿Reclasificar todas las URLs?
          </h3>
          <p className="text-sm text-yellow-700 mb-3">
            Has modificado una categoría. Para mantener la consistencia, se recomienda reclasificar todas las URLs.
            Esto puede tardar varios minutos y consumirá créditos de la API de LLM.
          </p>
          <div className="flex space-x-3">
            <button
              onClick={() => handleReclassify([modifiedCategoryId!])}
              className="bg-yellow-600 text-white px-4 py-2 rounded-md hover:bg-yellow-700 text-sm"
            >
              Reclasificar Ahora
            </button>
            <button
              onClick={() => {
                setShowReclassifyPrompt(false);
                setModifiedCategoryId(null);
              }}
              className="bg-gray-300 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-400 text-sm"
            >
              Más Tarde
            </button>
          </div>
        </div>
      )}

      {/* Categories Table */}
      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Nombre
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Descripción
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                URLs
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {categories.map((category) => (
              <tr key={category.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {category.id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {category.name}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                  {category.description}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                    {category.url_count}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                  <button
                    onClick={() => setEditingCategory(category)}
                    className="text-indigo-600 hover:text-indigo-900"
                  >
                    Editar
                  </button>
                  {category.id !== 'otros' && (
                    <button
                      onClick={() => handleDelete(category.id, category.name)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Eliminar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CategoryModal
          title="Nueva Categoría"
          onClose={() => setShowCreateModal(false)}
          onSubmit={handleCreate}
        />
      )}

      {/* Edit Modal */}
      {editingCategory && (
        <CategoryModal
          title="Editar Categoría"
          category={editingCategory}
          onClose={() => setEditingCategory(null)}
          onSubmit={(data) => handleUpdate(editingCategory.id, data)}
        />
      )}
    </div>
  );
}

// Category Modal Component
interface CategoryModalProps {
  title: string;
  category?: Category;
  onClose: () => void;
  onSubmit: (data: any) => void;
}

function CategoryModal({ title, category, onClose, onSubmit }: CategoryModalProps) {
  const [formData, setFormData] = useState({
    id: category?.id || '',
    name: category?.name || '',
    description: category?.description || '',
    consolidates: category?.consolidates?.join(', ') || '',
    examples: category?.examples?.join('\n') || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      ...(category ? {} : { id: formData.id }),
      name: formData.name,
      description: formData.description,
      consolidates: formData.consolidates.split(',').map(s => s.trim()).filter(Boolean),
      examples: formData.examples.split('\n').map(s => s.trim()).filter(Boolean),
    });
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <span className="text-2xl">&times;</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!category && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                ID (identificador único)
              </label>
              <input
                type="text"
                value={formData.id}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                className="w-full border border-gray-300 rounded-md px-3 py-2"
                required
                pattern="[a-z_]+"
                title="Solo letras minúsculas y guiones bajos"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Nombre
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Descripción
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              rows={3}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Consolida (categorías previas, separadas por coma)
            </label>
            <input
              type="text"
              value={formData.consolidates}
              onChange={(e) => setFormData({ ...formData, consolidates: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              placeholder="ej: politica, nacional, justicia"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Ejemplos (uno por línea)
            </label>
            <textarea
              value={formData.examples}
              onChange={(e) => setFormData({ ...formData, examples: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              rows={5}
              placeholder="Gobierno anuncia reforma educativa&#10;Congreso aprueba nueva ley"
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="bg-gray-300 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-400"
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
            >
              Guardar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
