'use client';

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';
import SourceCookieManagement from './SourceCookieManagement';

interface Source {
  id: number;
  name: string;
  display_name: string;
  base_url: string;
  language: string;
  description: string | null;
  is_active: boolean;
  priority: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface CookieInfo {
  domain: string;
  status: 'active' | 'invalid' | 'expired' | 'not_tested';
  cookie_count: number;
  file_path: string;
  file_size: number;
  created_at: string;
  last_tested_at: string | null;
  last_test_result: string | null;
  source_id: number | null;
  source_name: string | null;
  has_expired_cookies: boolean;
  expiring_soon: boolean;
  days_until_expiry: number | null;
}

export default function SourcesManagement() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingSource, setEditingSource] = useState<Source | null>(null);
  const [expandedSource, setExpandedSource] = useState<number | null>(null);
  const [cookiesByDomain, setCookiesByDomain] = useState<Record<string, CookieInfo>>({});
  const [cookieUploading, setCookieUploading] = useState(false);
  const [cookieTesting, setCookieTesting] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    display_name: '',
    base_url: '',
    language: 'es',
    description: '',
    is_active: true,
    priority: 1,
    notes: ''
  });

  useEffect(() => {
    fetchSources();
    fetchAllCookies();
  }, []);

  // Close modal on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showForm) {
        resetForm();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showForm]);

  const fetchSources = async () => {
    try {
      const response = await apiClient.get('/sources', {
        params: { include_inactive: true }
      });
      setSources(response.data);
      setError('');
    } catch (err: any) {
      setError('Error al cargar sources');
    } finally {
      setLoading(false);
    }
  };

  const fetchAllCookies = async () => {
    try {
      const response = await apiClient.get('/cookies');
      const cookiesMap: Record<string, CookieInfo> = {};

      response.data.cookies.forEach((cookie: CookieInfo) => {
        cookiesMap[cookie.domain] = cookie;
      });

      setCookiesByDomain(cookiesMap);
    } catch (err: any) {
      console.error('Error loading cookies:', err);
    }
  };

  const extractDomainFromUrl = (url: string): string => {
    try {
      const urlObj = new URL(url);
      return urlObj.hostname.replace('www.', '');
    } catch {
      return '';
    }
  };

  const toggleSourceExpansion = (sourceId: number) => {
    setExpandedSource(expandedSource === sourceId ? null : sourceId);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      display_name: '',
      base_url: '',
      language: 'es',
      description: '',
      is_active: true,
      priority: 1,
      notes: ''
    });
    setEditingSource(null);
    setShowForm(false);
  };

  const handleEdit = (source: Source) => {
    setFormData({
      name: source.name,
      display_name: source.display_name,
      base_url: source.base_url,
      language: source.language,
      description: source.description || '',
      is_active: source.is_active,
      priority: source.priority,
      notes: source.notes || ''
    });
    setEditingSource(source);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      if (editingSource) {
        // Update
        await apiClient.put(`/sources/${editingSource.id}`, formData);
      } else {
        // Create
        await apiClient.post('/sources', formData);
      }

      await fetchSources();
      resetForm();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al guardar source');
    }
  };

  const toggleActive = async (source: Source) => {
    try {
      await apiClient.put(`/sources/${source.id}`, {
        is_active: !source.is_active
      });
      await fetchSources();
    } catch (err: any) {
      alert('Error al cambiar estado');
    }
  };

  const handleDelete = async (source: Source) => {
    if (!confirm(`¿Eliminar source "${source.display_name}"?`)) return;

    try {
      await apiClient.delete(`/sources/${source.id}`);
      await fetchSources();
    } catch (err: any) {
      alert('Error al eliminar source');
    }
  };

  if (loading) return <div>Cargando...</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Gestión de Sources</h2>
        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
        >
          ➕ Nueva Source
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showForm && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={resetForm}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h3 className="text-lg font-medium">
                {editingSource ? 'Editar Source' : 'Nueva Source'}
              </h3>
              <button
                type="button"
                onClick={resetForm}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                ×
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  ID único *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  required
                  disabled={!!editingSource}
                  placeholder="elconfidencial"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md disabled:bg-gray-100"
                />
                <p className="text-xs text-gray-500 mt-1">Solo letras minúsculas, sin espacios</p>
              </div>

              {/* Display Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nombre mostrado *
                </label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({...formData, display_name: e.target.value})}
                  required
                  placeholder="El Confidencial"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              {/* Base URL */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  URL base *
                </label>
                <input
                  type="url"
                  value={formData.base_url}
                  onChange={(e) => setFormData({...formData, base_url: e.target.value})}
                  required
                  placeholder="https://www.example.com/"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              {/* Language */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Idioma
                </label>
                <select
                  value={formData.language}
                  onChange={(e) => setFormData({...formData, language: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="es">Español</option>
                  <option value="en">Inglés</option>
                  <option value="fr">Francés</option>
                  <option value="de">Alemán</option>
                  <option value="zh">Chino</option>
                  <option value="ja">Japonés</option>
                </select>
              </div>

              {/* Priority */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prioridad (1-100)
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={formData.priority}
                  onChange={(e) => setFormData({...formData, priority: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              {/* Description */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Descripción
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  rows={2}
                  placeholder="Descripción de la fuente"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              {/* Notes */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notas internas
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData({...formData, notes: e.target.value})}
                  rows={2}
                  placeholder="Notas técnicas o administrativas"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              {/* Active */}
              <div className="md:col-span-2">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                    className="rounded mr-2"
                  />
                  <span className="text-sm font-medium text-gray-700">Activa</span>
                </label>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t">
              <button
                type="submit"
                className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700"
              >
                💾 Guardar
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="bg-gray-300 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-400"
              >
                Cancelar
              </button>
            </div>
          </form>
          </div>
        </div>
      )}

      {/* Sources Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase w-8"></th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nombre</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">URL Base</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Idioma</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Prioridad</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cookies</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Acciones</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sources.map((source) => {
              const domain = extractDomainFromUrl(source.base_url);
              const cookieInfo = cookiesByDomain[domain];
              const isExpanded = expandedSource === source.id;

              return (
                <React.Fragment key={source.id}>
                  <tr className={isExpanded ? 'bg-gray-50' : ''}>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleSourceExpansion(source.id)}
                        className="text-gray-400 hover:text-gray-600 font-bold text-lg"
                      >
                        {isExpanded ? '▼' : '▶'}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <div className="font-medium text-gray-900">{source.display_name}</div>
                        <div className="text-sm text-gray-500">{source.name}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <a href={source.base_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">
                        {source.base_url && source.base_url.length > 40 ? source.base_url.substring(0, 40) + '...' : source.base_url}
                      </a>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{source.language ? source.language.toUpperCase() : 'N/A'}</td>
                    <td className="px-6 py-4 text-sm text-gray-900">{source.priority}</td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleActive(source)}
                        className={`px-2 py-1 text-xs font-medium rounded-full ${
                          source.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {source.is_active ? 'Activa' : 'Inactiva'}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      {cookieInfo ? (
                        <div className="flex items-center gap-1">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            cookieInfo.status === 'active' ? 'bg-green-100 text-green-800' :
                            cookieInfo.status === 'invalid' ? 'bg-red-100 text-red-800' :
                            cookieInfo.status === 'expired' ? 'bg-orange-100 text-orange-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            🍪 {cookieInfo.cookie_count}
                          </span>
                          {cookieInfo.has_expired_cookies && (
                            <span
                              className="text-red-600 text-lg cursor-help"
                              title={`Cookies caducadas (${cookieInfo.days_until_expiry !== null && cookieInfo.days_until_expiry < 0 ? `hace ${Math.abs(cookieInfo.days_until_expiry)} días` : 'caducadas'})`}
                            >
                              ❌
                            </span>
                          )}
                          {!cookieInfo.has_expired_cookies && cookieInfo.expiring_soon && cookieInfo.days_until_expiry !== null && (
                            <span
                              className="text-orange-500 text-lg cursor-help"
                              title={`Cookies caducan en ${cookieInfo.days_until_expiry} día${cookieInfo.days_until_expiry !== 1 ? 's' : ''}`}
                            >
                              ⚠️
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400 text-xs">Sin cookies</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm space-x-2">
                      <button
                        onClick={() => handleEdit(source)}
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        ✏️ Editar
                      </button>
                      <button
                        onClick={() => handleDelete(source)}
                        className="text-red-600 hover:text-red-900"
                      >
                        🗑️ Eliminar
                      </button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={8} className="px-6 py-4 bg-gray-50">
                        <SourceCookieManagement
                          domain={domain}
                          cookieInfo={cookieInfo || null}
                          onCookiesUpdated={fetchAllCookies}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
