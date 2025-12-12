'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';

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
  created_at: string;
  updated_at: string;
}

interface NewsletterConfigsContextType {
  configs: NewsletterConfig[];
  loading: boolean;
  error: string | null;
  refreshConfigs: () => Promise<void>;
}

const NewsletterConfigsContext = createContext<NewsletterConfigsContextType | undefined>(undefined);

export function NewsletterConfigsProvider({ children }: { children: React.ReactNode }) {
  const [configs, setConfigs] = useState<NewsletterConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load configs on mount
  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get('/newsletter-configs', {
        params: { only_active: true },
      });
      // Filter for active configs only
      const activeConfigs = response.data.filter((config: NewsletterConfig) => config.is_active);
      setConfigs(activeConfigs);
    } catch (err) {
      console.error('[NewsletterConfigsContext] Failed to load configs:', err);
      setError('Failed to load newsletter configurations');
      setConfigs([]);
    } finally {
      setLoading(false);
    }
  };

  const refreshConfigs = async () => {
    await loadConfigs();
  };

  return (
    <NewsletterConfigsContext.Provider
      value={{
        configs,
        loading,
        error,
        refreshConfigs,
      }}
    >
      {children}
    </NewsletterConfigsContext.Provider>
  );
}

export function useNewsletterConfigs() {
  const context = useContext(NewsletterConfigsContext);
  if (!context) {
    throw new Error('useNewsletterConfigs must be used within NewsletterConfigsProvider');
  }
  return context;
}
