'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { newsletterApi, newsletterConfigsApi, newsletterSubscriptionsApi } from '@/lib/api-client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { renderToStaticMarkup } from 'react-dom/server';
import { Bell, BookOpen, Clock, Rss, ShieldCheck, Sparkles, TrendingUp, Building2, Globe2, Banknote, Laptop, Users, Trophy, Tag, Copy, Check } from 'lucide-react';
import Footer from '@/components/Footer';
import { markdownToPlainText } from '@/lib/markdown-to-plain-text';

type NewsletterConfig = {
  id: number;
  name: string;
  display_name?: string | null;
  description?: string | null;
  visibility?: 'public' | 'private';
  is_active?: boolean;
  created_by_user_id?: number | null;
};

type NewsletterEdition = {
  id: number;
  newsletter_name: string;
  run_date: string;
  generated_at?: string | null;
  content_markdown?: string | null;
  content_html?: string | null;
  template_name?: string | null;
  articles_count?: number | null;
  categories?: string[] | null;
};

const parseDateValue = (value?: string | null) => {
  if (!value) return 0;
  const direct = Date.parse(value);
  if (!Number.isNaN(direct)) return direct;
  return Date.parse(`${value}T00:00:00Z`);
};

// Category to icon mapping
const CATEGORY_ICONS: Record<string, any> = {
  economia: TrendingUp,
  politica: Building2,
  geopolitica: Globe2,
  finanzas: Banknote,
  tecnologia: Laptop,
  sociedad: Users,
  deportes: Trophy,
  otros: Tag,
};

// Category display names (Spanish-friendly)
const CATEGORY_LABELS: Record<string, string> = {
  economia: 'Economía',
  politica: 'Política',
  geopolitica: 'Geopolítica',
  finanzas: 'Finanzas',
  tecnologia: 'Tecnología',
  sociedad: 'Sociedad',
  deportes: 'Deportes',
  otros: 'Otros',
};

// Category colors (Tailwind classes)
const CATEGORY_COLORS: Record<string, string> = {
  economia: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  politica: 'bg-blue-50 text-blue-700 ring-blue-200',
  geopolitica: 'bg-purple-50 text-purple-700 ring-purple-200',
  finanzas: 'bg-green-50 text-green-700 ring-green-200',
  tecnologia: 'bg-cyan-50 text-cyan-700 ring-cyan-200',
  sociedad: 'bg-pink-50 text-pink-700 ring-pink-200',
  deportes: 'bg-orange-50 text-orange-700 ring-orange-200',
  otros: 'bg-gray-50 text-gray-700 ring-gray-200',
};

const escapeHtml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const formatName = (name: string) =>
  name
    .replace(/[_-]+/g, ' ')
    .replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

const renderMarkdownToHtml = (markdown: string) =>
  renderToStaticMarkup(<ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>);

const htmlToPlainText = (html: string) => {
  if (typeof window === 'undefined') return '';
  const div = document.createElement('div');
  div.innerHTML = html;
  return div.innerText;
};

const cleanEditionContent = (edition: NewsletterEdition) => {
  const raw = edition.content_markdown || '';
  if (!raw) return raw;

  const slug = edition.newsletter_name?.toLowerCase();
  const lines = raw.split('\n');
  const cleaned = lines.filter((line, idx) => {
    const trimmed = line.trim();
    if (!trimmed && idx < 2) return false;
    const lower = trimmed.toLowerCase();

    // Filter newsletter name variations (with underscores, dashes, spaces)
    if (slug && (lower === slug || lower === slug.replace(/_/g, ' ') || lower === slug.replace(/-/g, ' '))) return false;

    // Filter metadata lines (multiple asterisk variations for bold)
    // Matches: Fecha:, *Fecha:, **Fecha:, *Fecha:*, **Fecha:**, etc.
    if (/^\*{0,2}fecha:\*{0,2}/i.test(trimmed)) return false;
    if (/^\*{0,2}generado:\*{0,2}/i.test(trimmed)) return false;
    if (/^\*{0,2}art[íi]culos?\s+totales?:\*{0,2}/i.test(trimmed)) return false;
    if (/^\*{0,2}plantilla:\*{0,2}/i.test(trimmed)) return false;
    if (/^\*{0,2}categor[íi]as?:\*{0,2}/i.test(trimmed)) return false;

    // Filter horizontal rules (---, ***, ___)
    if (/^[\*\-_]{3,}$/.test(trimmed)) return false;

    // Filter lines that look like "newsletter_name" or similar
    if (/^[a-z_-]+newsletter$/i.test(trimmed)) return false;
    if (/^newsletter[a-z_-]*$/i.test(trimmed)) return false;

    // Filter headers that are just the newsletter name in various formats
    if (/^#{1,6}\s*[a-z_-]*newsletter[a-z_-]*$/i.test(trimmed)) return false;
    if (slug && /^#{1,6}\s*/.test(trimmed) && trimmed.toLowerCase().includes(slug)) return false;

    // Filter standalone links at the end (lines that are just a markdown link, typically article titles)
    // This matches lines like: [**Fed cuts rate but future easing uncertain**](https://...)
    if (/^\[[\*\*]*[^\]]+[\*\*]*\]\(https?:\/\/[^\)]+\)$/.test(trimmed)) return false;

    return true;
  });
  return cleaned.join('\n').trim();
};

const getExcerpt = (markdown?: string | null, maxLength: number = 180) => {
  if (!markdown) return '';
  const plain = markdown.replace(/[#>*_`\-\n]/g, ' ').replace(/\s+/g, ' ').trim();
  return plain.length > maxLength ? `${plain.slice(0, maxLength)}…` : plain;
};

const CategoryBadge = ({ category }: { category: string }) => {
  const Icon = CATEGORY_ICONS[category] || Tag;
  const label = CATEGORY_LABELS[category] || category;
  const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.otros;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ring-1 ${colors}`}>
      <Icon className="w-3.5 h-3.5" />
      {label}
    </span>
  );
};

const getRelativeDateString = (dateString?: string | null, includeYear: boolean = false) => {
  if (!dateString) return '';

  const publishDate = new Date(dateString);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const pubDate = new Date(publishDate.getFullYear(), publishDate.getMonth(), publishDate.getDate());

  const timeString = publishDate.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit'
  });

  if (pubDate.getTime() === today.getTime()) {
    return `Hoy · ${timeString}`;
  } else if (pubDate.getTime() === yesterday.getTime()) {
    return `Ayer · ${timeString}`;
  } else {
    const dateFormat: Intl.DateTimeFormatOptions = includeYear
      ? { year: 'numeric', month: 'short', day: 'numeric' }
      : { day: 'numeric', month: 'short' };
    return publishDate.toLocaleDateString('es-ES', dateFormat) + ' · ' + timeString;
  }
};

export default function DashboardPage() {
  const { user } = useAuth();

  const [configs, setConfigs] = useState<NewsletterConfig[]>([]);
  const [editions, setEditions] = useState<NewsletterEdition[]>([]);
  const [subscriptions, setSubscriptions] = useState<string[]>([]);
  const [selectedEdition, setSelectedEdition] = useState<NewsletterEdition | null>(null);
  const [loadingBase, setLoadingBase] = useState(true);
  const [loadingFeed, setLoadingFeed] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedLimit, setFeedLimit] = useState(60);
  const [feedFilter, setFeedFilter] = useState<'all' | 'private'>('all');
  const [hasMore, setHasMore] = useState(true);
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);

  const renderMarkdownAsHtml = useCallback(
    (markdown: string) =>
      renderToStaticMarkup(<ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>),
    []
  );
  // Backwards compatibility with previous helper name used in handlers.
  const renderMarkdownToHtml = renderMarkdownAsHtml;


  useEffect(() => {
    if (!user) return;
    let mounted = true;

    const loadData = async () => {
      setLoadingBase(true);
      setError(null);
      try {
        const [configRes, subsRes] = await Promise.all([
          newsletterConfigsApi.list(true),
          newsletterSubscriptionsApi.list(),
        ]);

        if (!mounted) return;
        setConfigs(configRes.data || []);
        const names = (subsRes.data || []).map((sub: any) => sub.newsletter_name);
        setSubscriptions(names);
      } catch (err) {
        console.error('Error cargando datos del dashboard', err);
        if (mounted) {
          setError('No pudimos cargar tus newsletters. Intenta de nuevo en unos segundos.');
        }
      } finally {
        if (mounted) setLoadingBase(false);
      }
    };

    loadData();
    return () => {
      mounted = false;
    };
  }, [user]);

  const fetchFeed = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!user) return;
      if (!options?.silent) setLoadingFeed(true);
      try {
        const latestRes = await newsletterApi.getLatest(feedLimit);
        const nextEditions = latestRes.data || [];
        setEditions(nextEditions);
        setHasMore(nextEditions.length >= feedLimit);
      } catch (err) {
        console.error('Error cargando ediciones del feed', err);
        setError('No pudimos cargar las ediciones. Intenta nuevamente.');
      } finally {
        if (!options?.silent) setLoadingFeed(false);
        setLoadingMore(false);
      }
    },
    [feedLimit, user]
  );

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchFeed({ silent: true });
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchFeed]);

  const privateConfigs = useMemo(() => {
    if (!user || user.role !== 'enterprise') return [];
    return configs.filter((cfg) => cfg.visibility === 'private');
  }, [configs, user]);

  const privateSubscribed = useMemo(() => {
    if (!user) return [];
    return configs.filter(
      (cfg) => cfg.visibility === 'private' && subscriptions.includes(cfg.name)
    );
  }, [configs, subscriptions, user]);

  const configByName = useMemo(() => {
    const map: Record<string, NewsletterConfig> = {};
    configs.forEach((cfg) => {
      map[cfg.name] = cfg;
    });
    return map;
  }, [configs]);

  useEffect(() => {
    if (feedFilter === 'private' && privateSubscribed.length === 0) {
      setFeedFilter('all');
    }
  }, [feedFilter, privateSubscribed.length]);

  const orderedFeed = useMemo(() => {
    const sorted = [...editions].sort(
      (a, b) =>
        parseDateValue(b.generated_at || b.run_date) -
        parseDateValue(a.generated_at || a.run_date)
    );

    if (!subscriptions.length) return [];
    const subscribed = sorted.filter((edition) => subscriptions.includes(edition.newsletter_name));
    if (feedFilter === 'private') {
      return subscribed.filter(
        (edition) => configByName[edition.newsletter_name]?.visibility === 'private'
      );
    }
    return subscribed;
  }, [editions, subscriptions, feedFilter, configByName]);

  useEffect(() => {
    if (!orderedFeed.length) {
      setSelectedEdition(null);
      return;
    }

    const alreadySelected = orderedFeed.find((edition) => edition.id === selectedEdition?.id);
    if (!alreadySelected) {
      setSelectedEdition(orderedFeed[0]);
    }
  }, [orderedFeed, selectedEdition?.id]);

  if (!user) {
    return null;
  }

  const handleToggleSubscription = (name: string) => {
    const isSubscribed = subscriptions.includes(name);
    const action = isSubscribed ? newsletterSubscriptionsApi.unsubscribe : newsletterSubscriptionsApi.subscribe;
    action(name)
      .then(() => {
        setSubscriptions((prev) =>
          isSubscribed ? prev.filter((item) => item !== name) : [...prev, name]
        );
      })
      .catch((err) => {
        console.error('No se pudo actualizar la suscripción', err);
        setError('No pudimos actualizar tu suscripción. Intenta nuevamente.');
      });
  };

  const resolveName = (name: string) => {
    const found = configs.find((cfg) => cfg.name === name);
    return found?.display_name || formatName(name);
  };

  const isTodayEdition = (edition: NewsletterEdition) => {
    const dateValue = parseDateValue(edition.generated_at || edition.run_date);
    if (!dateValue) return false;
    const target = new Date(dateValue);
    const now = new Date();
    return (
      target.getFullYear() === now.getFullYear() &&
      target.getMonth() === now.getMonth() &&
      target.getDate() === now.getDate()
    );
  };

  const handleLoadMore = () => {
    setLoadingMore(true);
    setFeedLimit((prev) => prev + 30);
  };

  const handleExportPdf = () => {
    if (!selectedEdition) return;
    const cleanedMarkdown = cleanEditionContent(selectedEdition);
    const printableContent =
      cleanedMarkdown
        ? renderMarkdownAsHtml(cleanedMarkdown)
        : selectedEdition.content_html ||
          `<p>${escapeHtml('Contenido no disponible.')}</p>`;
    const title = resolveName(selectedEdition.newsletter_name);
    const dateLabel =
      selectedEdition.generated_at
        ? new Date(selectedEdition.generated_at).toLocaleString()
        : selectedEdition.run_date;

    const doc = window.open('', '_blank', 'width=900,height=700');
    if (!doc) return;
    doc.document.write(`
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <title>${title} - ${selectedEdition.run_date}</title>
          <style>
            body { font-family: 'Inter', system-ui, -apple-system, sans-serif; padding: 32px; color: #111827; background: #f8fafc; }
            h1 { margin: 0 0 4px 0; font-size: 24px; }
            h2 { margin: 0 0 16px 0; font-size: 15px; color: #4b5563; font-weight: 500; }
            .content { background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 1px 8px rgba(0,0,0,0.06); }
            .content p { margin: 0 0 12px 0; text-align: justify; }
          </style>
        </head>
        <body>
          <h1>${title}</h1>
          <h2>${dateLabel}</h2>
          <div class="content">${printableContent}</div>
        </body>
      </html>
    `);
    doc.document.close();
    doc.focus();
    doc.print();
  };

  const handleEmailEdition = () => {
    if (!selectedEdition) return;
    const subject = encodeURIComponent(
      `Newsletter ${resolveName(selectedEdition.newsletter_name)} - ${selectedEdition.run_date}`
    );
    const cleanedMarkdown = cleanEditionContent(selectedEdition);

    // Convert markdown to enriched plain text (preserves links, headers, emphasis)
    const bodyText = cleanedMarkdown
      ? markdownToPlainText(cleanedMarkdown)
      : (selectedEdition.content_markdown
          ? markdownToPlainText(selectedEdition.content_markdown)
          : 'Contenido no disponible.');

    // mailto: has length limitations (~2000 chars for body in some clients)
    // If content is too long, truncate with warning
    const maxBodyLength = 1800; // Conservative limit
    const intro = `Hola,\n\nTe comparto la edición ${selectedEdition.run_date} de ${resolveName(
      selectedEdition.newsletter_name
    )}:\n\n`;
    const outro = '\n\nEnviado desde el dashboard de newsletters.';

    let finalBody = bodyText;
    const totalLength = intro.length + bodyText.length + outro.length;

    if (totalLength > maxBodyLength) {
      const availableLength = maxBodyLength - intro.length - outro.length - 100; // Reserve for truncation msg
      finalBody = bodyText.substring(0, availableLength) +
        '\n\n[... Contenido truncado por límites de email. Usa "Exportar PDF" para el contenido completo ...]';
    }

    const body = encodeURIComponent(intro + finalBody + outro);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  const handleCopyHtmlForEmail = async () => {
    if (!selectedEdition) return;

    const cleanedMarkdown = cleanEditionContent(selectedEdition);
    const htmlContent = cleanedMarkdown
      ? renderMarkdownAsHtml(cleanedMarkdown)
      : (selectedEdition.content_markdown
          ? renderMarkdownAsHtml(selectedEdition.content_markdown)
          : '<p>Contenido no disponible.</p>');

    // Create a well-formatted HTML email with inline styles
    const emailHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 650px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      color: #1a1a1a;
      font-size: 24px;
      margin-top: 24px;
      margin-bottom: 12px;
      border-bottom: 2px solid #e5e7eb;
      padding-bottom: 8px;
    }
    h2 {
      color: #374151;
      font-size: 20px;
      margin-top: 20px;
      margin-bottom: 10px;
    }
    h3 {
      color: #4b5563;
      font-size: 16px;
      margin-top: 16px;
      margin-bottom: 8px;
    }
    p {
      margin: 0 0 12px 0;
      text-align: justify;
    }
    a {
      color: #2563eb;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    strong {
      color: #1f2937;
      font-weight: 600;
    }
    ul, ol {
      margin: 12px 0;
      padding-left: 24px;
    }
    li {
      margin-bottom: 6px;
    }
    blockquote {
      margin: 16px 0;
      padding: 12px 20px;
      border-left: 4px solid #e5e7eb;
      background: #f9fafb;
      color: #6b7280;
    }
    hr {
      border: none;
      border-top: 1px solid #e5e7eb;
      margin: 24px 0;
    }
    .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 24px;
    }
    .header h1 {
      color: white;
      border: none;
      margin: 0;
      padding: 0;
      font-size: 22px;
    }
    .header p {
      margin: 8px 0 0 0;
      opacity: 0.9;
      font-size: 14px;
    }
    .footer {
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid #e5e7eb;
      font-size: 12px;
      color: #9ca3af;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>${resolveName(selectedEdition.newsletter_name)}</h1>
    <p>Edición del ${selectedEdition.run_date}</p>
  </div>

  <div class="content">
    ${htmlContent}
  </div>

  <div class="footer">
    Newsletter generada desde el dashboard
  </div>
</body>
</html>
    `.trim();

    try {
      // Use Clipboard API to copy HTML
      const clipboardItem = new ClipboardItem({
        'text/html': new Blob([emailHtml], { type: 'text/html' }),
        'text/plain': new Blob([emailHtml], { type: 'text/plain' })
      });

      await navigator.clipboard.write([clipboardItem]);

      // Show success feedback
      setCopiedToClipboard(true);
      setTimeout(() => setCopiedToClipboard(false), 3000);
    } catch (err) {
      console.error('Error copiando al portapapeles:', err);
      // Fallback: copy as plain text
      try {
        await navigator.clipboard.writeText(emailHtml);
        setCopiedToClipboard(true);
        setTimeout(() => setCopiedToClipboard(false), 3000);
      } catch (fallbackErr) {
        console.error('Error en fallback:', fallbackErr);
        setError('No se pudo copiar al portapapeles. Intenta nuevamente.');
      }
    }
  };

  const isInitialLoading = loadingBase || (loadingFeed && editions.length === 0);

  const renderConfigCard = (cfg: NewsletterConfig, variant: 'public' | 'private') => {
    const isSubscribed = subscriptions.includes(cfg.name);
    const badgeStyles =
      variant === 'private'
        ? 'bg-orange-100 text-orange-700 ring-1 ring-orange-200'
        : 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200';

    return (
      <div
        key={cfg.id}
        className="flex items-start justify-between rounded-2xl border border-gray-100 bg-white p-4 shadow-sm hover:-translate-y-0.5 hover:shadow-md transition-all"
      >
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${badgeStyles}`}>
              {variant === 'private' ? <ShieldCheck className="w-4 h-4" /> : <Rss className="w-4 h-4" />}
              {variant === 'private' ? 'Privada' : 'Pública'}
            </span>
            {!cfg.is_active && (
              <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-full ring-1 ring-amber-100">
                Inactiva
              </span>
            )}
          </div>
          <div className="font-semibold text-gray-900">{cfg.display_name || formatName(cfg.name)}</div>
          <p className="text-sm text-gray-600">{cfg.description || 'Sin descripción'}</p>
        </div>
        <button
          onClick={() => handleToggleSubscription(cfg.name)}
          className={`ml-4 inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition-all ${
            isSubscribed
              ? 'bg-gray-100 text-gray-800 hover:bg-gray-200'
              : 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md hover:shadow-lg'
          }`}
        >
          {isSubscribed ? 'Quitar' : 'Suscribirme'}
        </button>
      </div>
    );
  };

  const renderFeedItem = (edition: NewsletterEdition) => {
    const isActive = selectedEdition?.id === edition.id;
    const displayName = resolveName(edition.newsletter_name);
    const isPrivate = configByName[edition.newsletter_name]?.visibility === 'private';
    const isToday = isTodayEdition(edition);
    const dateTimeString = getRelativeDateString(edition.generated_at) || edition.run_date;

    // Base styles - removed special today styling
    const baseClasses = 'w-full text-left rounded-lg border p-3.5 transition-all relative overflow-hidden';
    const activeClasses = 'border-indigo-300 bg-indigo-50 shadow-sm';
    const idleClasses = 'border-gray-200 bg-white hover:border-indigo-200 hover:shadow-sm';

    return (
      <button
        key={edition.id}
        onClick={() => setSelectedEdition(edition)}
        className={`${baseClasses} ${
          isActive ? activeClasses : idleClasses
        }`}
      >
        {/* Header Row: Date & Time + Private Badge */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-xs text-gray-600">
            {/* Today indicator - subtle green dot (no animation) */}
            {isToday && (
              <span className="inline-flex h-2 w-2 rounded-full bg-green-500"></span>
            )}
            <Clock className="w-3.5 h-3.5" />
            <span className="font-medium">
              {dateTimeString}
            </span>
          </div>
          {isPrivate && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-semibold text-orange-700 bg-orange-50 ring-1 ring-orange-200">
              <ShieldCheck className="w-3.5 h-3.5" />
              Privada
            </span>
          )}
        </div>

        {/* Newsletter Name as Title - Cool Typography */}
        <div className="mt-2.5">
          <h3 className="text-base font-bold text-transparent bg-clip-text bg-gradient-to-r from-gray-900 via-indigo-900 to-purple-900 leading-tight tracking-tight">
            {displayName}
          </h3>
        </div>

        {/* Footer: Category Icons Only */}
        <div className="mt-2 flex items-center gap-1.5 flex-wrap">
          {edition.categories && edition.categories.length > 0 ? (
            <>
              {edition.categories.map((category, idx) => {
                const Icon = CATEGORY_ICONS[category] || Tag;
                const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.otros;
                return (
                  <span
                    key={idx}
                    className={`inline-flex items-center justify-center p-1.5 rounded-md ring-1 ${colors}`}
                    title={CATEGORY_LABELS[category] || category}
                  >
                    <Icon className="w-3 h-3" />
                  </span>
                );
              })}
            </>
          ) : null}
        </div>
      </button>
    );
  };

  if (isInitialLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="bg-white border border-gray-100 rounded-3xl shadow-sm p-8">
          <div className="flex items-center gap-3">
            <Sparkles className="w-6 h-6 text-indigo-500 animate-pulse" />
            <div>
              <div className="h-4 w-48 bg-gray-100 rounded animate-pulse" />
              <div className="mt-2 h-3 w-64 bg-gray-100 rounded animate-pulse" />
            </div>
          </div>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((key) => (
              <div key={key} className="h-28 bg-gray-50 border border-gray-100 rounded-2xl animate-pulse" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-800">
          {error}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <BookOpen className="w-5 h-5 text-indigo-500" />
                Timeline de suscripciones
                <div className="flex items-center space-x-2 ml-2">
                  <div className="relative flex items-center justify-center">
                    <span className="absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75 animate-ping"></span>
                    <span className="absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-50 animate-pulse"></span>
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500"></span>
                  </div>
                  <span className="text-[11px] font-semibold text-green-600 tracking-wide">LIVE</span>
                </div>
              </div>
            </div>

            {privateSubscribed.length > 0 && (user.role === 'admin' || user.role === 'enterprise') && (
              <div className="flex justify-start">
                <div className="inline-flex items-center rounded-full bg-gray-100 p-0.5 shadow-inner border border-gray-200 text-xs font-semibold text-gray-700">
                  <button
                    onClick={() => setFeedFilter('all')}
                    className={`px-3 py-1 rounded-full transition ${
                      feedFilter === 'all'
                        ? 'bg-white text-indigo-700 shadow-sm'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Todas
                  </button>
                  <button
                    onClick={() => setFeedFilter('private')}
                    className={`px-3 py-1 rounded-full transition ${
                      feedFilter === 'private'
                        ? 'bg-white text-orange-700 shadow-sm'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    Privadas
                  </button>
                </div>
              </div>
            )}

            {orderedFeed.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-gray-600">
                Aún no hay ediciones de tus suscripciones.
              </div>
            ) : (
              <div className="space-y-3 lg:max-h-[calc(100vh-200px)] lg:overflow-y-auto lg:pr-1 lg:pb-2">
                {orderedFeed.map((edition) => renderFeedItem(edition))}
                {hasMore && (
                  <div className="pt-1">
                    <button
                      onClick={handleLoadMore}
                      disabled={loadingMore}
                      className="w-full rounded-xl border border-dashed border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-semibold text-indigo-700 hover:border-indigo-300 hover:bg-indigo-100 transition disabled:opacity-60"
                    >
                      {loadingMore ? 'Cargando más ediciones...' : 'Cargar más ediciones'}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {privateConfigs.length > 0 && (user.role === 'admin' || user.role === 'enterprise') && (
            <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <ShieldCheck className="w-5 h-5 text-orange-500" />
                Tus newsletters privadas
              </div>
              <div className="space-y-3">
                {privateConfigs.map((cfg) => renderConfigCard(cfg, 'private'))}
              </div>
            </div>
          )}
        </div>

        <div>
          <div className="rounded-3xl border border-gray-100 bg-white p-4 sm:p-5 shadow-sm h-full min-h-[420px] sm:min-h-[480px] md:min-h-[520px] lg:flex lg:flex-col">
            {!selectedEdition ? (
              <div className="h-full rounded-xl border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-gray-600">
                {subscriptions.length === 0
                  ? 'Suscríbete desde "Explorar" en la barra superior y luego selecciona una edición para leerla aquí.'
                  : 'Selecciona una edición del feed para verla aquí.'}
              </div>
            ) : (
              <div className="flex flex-col h-full">
                {(() => {
                  const isPrivate = configByName[selectedEdition.newsletter_name]?.visibility === 'private';
                  return (
                    <div className="space-y-3">
                      {/* Title Row */}
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <div className="flex items-center gap-2">
                          <div className="text-xl font-bold text-gray-900">
                            {resolveName(selectedEdition.newsletter_name)}
                          </div>
                          {isPrivate && (
                            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-semibold text-orange-700 bg-orange-50 ring-1 ring-orange-200">
                              <ShieldCheck className="w-4 h-4" />
                              Privada
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-wrap justify-end">
                          <button
                            onClick={handleExportPdf}
                            className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-800 shadow-sm hover:bg-gray-50 transition"
                          >
                            Exportar PDF
                          </button>
                          <button
                            onClick={handleCopyHtmlForEmail}
                            className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold shadow-sm transition ${
                              copiedToClipboard
                                ? 'border-green-200 bg-green-50 text-green-700'
                                : 'border-gray-200 bg-white text-gray-800 hover:bg-gray-50'
                            }`}
                          >
                            {copiedToClipboard ? (
                              <>
                                <Check className="w-4 h-4" />
                                ¡Copiado!
                              </>
                            ) : (
                              <>
                                <Copy className="w-4 h-4" />
                                Copiar para email
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Metadata Row */}
                      <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600">
                        {/* Publication Date & Time */}
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-4 h-4" />
                          <span>
                            {getRelativeDateString(selectedEdition.generated_at, true) || selectedEdition.run_date}
                          </span>
                        </div>

                        {/* Article Count */}
                        {selectedEdition.articles_count && (
                          <div className="flex items-center gap-1.5">
                            <BookOpen className="w-4 h-4" />
                            <span className="font-medium">
                              {selectedEdition.articles_count} {selectedEdition.articles_count === 1 ? 'artículo' : 'artículos'}
                            </span>
                          </div>
                        )}

                        {/* Category Badges */}
                        {selectedEdition.categories && selectedEdition.categories.length > 0 && (
                          <div className="flex items-center gap-2 flex-wrap">
                            {selectedEdition.categories.map((category, idx) => (
                              <CategoryBadge key={idx} category={category} />
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}
                <div className="mt-4 flex-1 prose prose-sm max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a: ({ node, ...props }) => (
                        <a {...props} target="_blank" rel="noopener noreferrer" />
                      )
                    }}
                  >
                    {cleanEditionContent(selectedEdition) || selectedEdition.content_markdown || 'Esta edición no tiene contenido markdown disponible.'}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}
