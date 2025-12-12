'use client';

import { useState } from 'react';
import { apiClient } from '@/lib/api-client';

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

interface SourceCookieManagementProps {
  domain: string;
  cookieInfo: CookieInfo | null;
  onCookiesUpdated: () => void;
}

export default function SourceCookieManagement({
  domain,
  cookieInfo,
  onCookiesUpdated
}: SourceCookieManagementProps) {
  const [uploading, setUploading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setUploadError(null);
      setTestResult(null);

      // Read file content
      const fileContent = await file.text();
      const cookies = JSON.parse(fileContent);

      // Upload with automatic validation
      const response = await apiClient.post('/cookies', {
        domain: domain,
        cookies: cookies,
        auto_validate: true
      });

      setTestResult(`✓ ${response.data.message}`);
      onCookiesUpdated();

    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Error al subir cookies';
      setUploadError(errorMsg);
      setTestResult(`✗ ${errorMsg}`);
    } finally {
      setUploading(false);
      // Reset file input
      e.target.value = '';
    }
  };

  const handleTestCookies = async () => {
    if (!cookieInfo) return;

    try {
      setTesting(true);
      setTestResult(null);
      setUploadError(null);

      const response = await apiClient.post('/cookies/test', {
        domain: domain
      });

      if (response.data.success) {
        setTestResult(`✓ ${response.data.message}`);
      } else {
        setUploadError(response.data.message);
        setTestResult(`✗ ${response.data.message}`);
      }

      onCookiesUpdated();

    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Error al testar cookies';
      setUploadError(errorMsg);
      setTestResult(`✗ ${errorMsg}`);
    } finally {
      setTesting(false);
    }
  };

  const handleDeleteCookies = async () => {
    if (!cookieInfo || !confirm('¿Eliminar cookies para este dominio?')) return;

    try {
      await apiClient.delete(`/cookies/${domain}`);
      setTestResult('✓ Cookies eliminadas');
      onCookiesUpdated();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Error al eliminar cookies';
      setUploadError(errorMsg);
    }
  };

  const getStatusBadge = (status: string) => {
    const badges = {
      active: 'bg-green-100 text-green-800',
      invalid: 'bg-red-100 text-red-800',
      expired: 'bg-orange-100 text-orange-800',
      not_tested: 'bg-gray-100 text-gray-800'
    };

    const labels = {
      active: '✓ Activas',
      invalid: '✗ Inválidas',
      expired: '⚠ Expiradas',
      not_tested: '? Sin testar'
    };

    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${badges[status as keyof typeof badges]}`}>
        {labels[status as keyof typeof labels]}
      </span>
    );
  };

  return (
    <div className="bg-gray-50 p-4 rounded-md border border-gray-200 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-gray-900">
          🍪 Cookies de Autenticación
        </h4>
        {cookieInfo && getStatusBadge(cookieInfo.status)}
      </div>

      {cookieInfo ? (
        <div className="space-y-3">
          {/* Cookie Info */}
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-500">Cookies:</span>{' '}
              <span className="font-medium">{cookieInfo.cookie_count}</span>
            </div>
            <div>
              <span className="text-gray-500">Tamaño:</span>{' '}
              <span className="font-medium">{(cookieInfo.file_size / 1024).toFixed(1)} KB</span>
            </div>
            <div className="col-span-2">
              <span className="text-gray-500">Creadas:</span>{' '}
              <span className="font-medium">
                {new Date(cookieInfo.created_at).toLocaleString('es-ES')}
              </span>
            </div>
            {cookieInfo.days_until_expiry !== null && (
              <div className="col-span-2">
                <span className="text-gray-500">Expiración:</span>{' '}
                <span className={`font-medium ${
                  cookieInfo.has_expired_cookies ? 'text-red-600' :
                  cookieInfo.expiring_soon ? 'text-orange-600' :
                  'text-green-600'
                }`}>
                  {cookieInfo.has_expired_cookies && cookieInfo.days_until_expiry < 0
                    ? `❌ Caducadas hace ${Math.abs(cookieInfo.days_until_expiry)} día${Math.abs(cookieInfo.days_until_expiry) !== 1 ? 's' : ''}`
                    : cookieInfo.expiring_soon
                    ? `⚠️ Caducan en ${cookieInfo.days_until_expiry} día${cookieInfo.days_until_expiry !== 1 ? 's' : ''}`
                    : `✓ Válidas (${cookieInfo.days_until_expiry} días restantes)`
                  }
                </span>
              </div>
            )}
          </div>

          {/* Test Result */}
          {testResult && (
            <div className={`p-2 rounded text-sm ${
              testResult.startsWith('✓')
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              {testResult}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={handleTestCookies}
              disabled={testing}
              className="flex-1 bg-blue-600 text-white px-3 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400 text-sm"
            >
              {testing ? '⏳ Testando...' : '🧪 Testar Cookies'}
            </button>

            <label className="flex-1 bg-indigo-600 text-white px-3 py-2 rounded-md hover:bg-indigo-700 text-sm text-center cursor-pointer">
              {uploading ? '⏳ Subiendo...' : '⬆️ Actualizar'}
              <input
                type="file"
                accept=".json"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
            </label>

            <button
              onClick={handleDeleteCookies}
              className="bg-red-600 text-white px-3 py-2 rounded-md hover:bg-red-700 text-sm"
            >
              🗑️
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            No hay cookies configuradas para este dominio.
          </p>

          {/* Test Result */}
          {testResult && (
            <div className={`p-2 rounded text-sm ${
              testResult.startsWith('✓')
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}>
              {testResult}
            </div>
          )}

          <label className="block">
            <div className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 text-sm text-center cursor-pointer">
              {uploading ? '⏳ Subiendo y validando...' : '⬆️ Subir Cookies (JSON)'}
            </div>
            <input
              type="file"
              accept=".json"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>

          <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-blue-800">
            <p className="font-medium mb-1">📋 Cómo exportar cookies:</p>
            <ol className="list-decimal list-inside space-y-1">
              <li>Usa una extensión como &quot;EditThisCookie&quot; o &quot;Cookie-Editor&quot;</li>
              <li>Navega a {domain} y haz login</li>
              <li>Exporta las cookies como JSON</li>
              <li>Sube el archivo aquí (se validará automáticamente)</li>
            </ol>
          </div>
        </div>
      )}

      {uploadError && !testResult && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
          {uploadError}
        </div>
      )}
    </div>
  );
}
