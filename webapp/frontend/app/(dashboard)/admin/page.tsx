'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter, useSearchParams } from 'next/navigation';
import Dashboard from '@/components/admin/Dashboard';
import UsersManagement from '@/components/admin/UsersManagement';
import CategoriesManagement from '@/components/admin/CategoriesManagement';
import APIKeyManagement from '@/components/admin/APIKeyManagement';
import SourcesManagement from '@/components/admin/SourcesManagement';
import StageExecutionManagement from '@/components/admin/StageExecutionManagement';
import NewsletterConfigManagement from '@/components/admin/newsletters/NewsletterConfigManagement';
import NewsletterExecutionHistory from '@/components/admin/newsletters/NewsletterExecutionHistory';
import SystemConfigManagement from '@/components/admin/newsletters/SystemConfigManagement';
import { NewsletterConfigsProvider } from '@/contexts/NewsletterConfigsContext';

type Tab = 'dashboard' | 'users' | 'categories' | 'api-keys' | 'sources' | 'stage-executions' | 'newsletters';

export default function AdminPage() {
  const { isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  useEffect(() => {
    if (!authLoading && !isAdmin) {
      router.push('/dashboard');
    }
  }, [isAdmin, authLoading, router]);

  useEffect(() => {
    // Read tab from URL query parameter
    const tab = searchParams.get('tab') as Tab;
    if (tab && ['dashboard', 'users', 'categories', 'api-keys', 'sources', 'stage-executions', 'newsletters'].includes(tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    // Update URL without reloading page
    window.history.pushState({}, '', `/admin?tab=${tab}`);
  };

  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="text-lg">Cargando...</div>
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-xl font-bold text-gray-900">Panel de Administración</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => handleTabChange('dashboard')}
            className={`
              py-2 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'dashboard'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            📊 Dashboard
          </button>
          <button
            onClick={() => handleTabChange('users')}
            className={`
              py-2 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'users'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            👥 Gestión de Usuarios
          </button>
          <button
            onClick={() => handleTabChange('categories')}
            className={`
              py-2 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'categories'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            📁 Gestión de Categorías
          </button>
          <button
            onClick={() => handleTabChange('api-keys')}
            className={`
              py-2 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'api-keys'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            🔑 Claves de API
          </button>
          <button
            onClick={() => handleTabChange('sources')}
            className={`
              py-2 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'sources'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            📰 Fuentes de Noticias
          </button>
          <button
            onClick={() => handleTabChange('stage-executions')}
            className={`
              py-2 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'stage-executions'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            🔄 Scraping de URLs
          </button>
          <button
            onClick={() => handleTabChange('newsletters')}
            className={`
              py-2 px-1 border-b-2 font-medium text-sm transition-colors
              ${activeTab === 'newsletters'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }
            `}
          >
            📧 Newsletters
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'users' && <UsersManagement />}
        {activeTab === 'categories' && <CategoriesManagement />}
        {activeTab === 'api-keys' && <APIKeyManagement />}
        {activeTab === 'sources' && <SourcesManagement />}
        {activeTab === 'stage-executions' && <StageExecutionManagement />}
        {activeTab === 'newsletters' && (
          <NewsletterConfigsProvider>
            <div className="space-y-8">
              <NewsletterExecutionHistory
                afterMainContent={
                  <div className="border-t pt-8">
                    <NewsletterConfigManagement />
                  </div>
                }
              />
              <div className="border-t pt-8">
                <SystemConfigManagement />
              </div>
            </div>
          </NewsletterConfigsProvider>
        )}
      </div>
    </div>
  );
}
