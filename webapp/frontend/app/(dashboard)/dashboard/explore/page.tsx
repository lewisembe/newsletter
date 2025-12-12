'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { newsletterConfigsApi, newsletterSubscriptionsApi, userApi } from '@/lib/api-client';
import { ArrowLeft, Rss, ShieldCheck, Sparkles, TrendingUp, Building2, Globe2, Banknote, Laptop, Users, Trophy, Tag, BookOpen, Clock, User } from 'lucide-react';
import Footer from '@/components/Footer';

type NewsletterConfig = {
  id: number;
  name: string;
  display_name?: string | null;
  description?: string | null;
  visibility?: 'public' | 'private';
  is_active?: boolean;
  created_by_user_id?: number | null;
  source_count?: number;
  categories?: string[];
  articles_count?: number;
  created_at?: string;
};

type UserListItem = {
  id: number;
  nombre: string;
  email: string;
  role: string;
};

// Category to icon mapping (same as dashboard)
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

// Category display names
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

// Category colors
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

export default function ExploreNewslettersPage() {
  const { user } = useAuth();
  const [configs, setConfigs] = useState<NewsletterConfig[]>([]);
  const [subscriptions, setSubscriptions] = useState<string[]>([]);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!user) return;
    let mounted = true;

    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const promises = [
          newsletterConfigsApi.list(true),
          newsletterSubscriptionsApi.list(),
        ];

        // If admin, also fetch users list
        if (user.role === 'admin') {
          promises.push(userApi.getAllUsers(false));
        }

        const results = await Promise.all(promises);

        if (!mounted) return;
        setConfigs(results[0].data || []);
        const names = (results[1].data || []).map((sub: any) => sub.newsletter_name);
        setSubscriptions(names);

        // Set users if admin
        if (user.role === 'admin' && results[2]) {
          setUsers(results[2].data || []);
        }
      } catch (err) {
        console.error('Error cargando newsletters', err);
        if (mounted) setError('No pudimos cargar las newsletters. Intenta de nuevo en unos segundos.');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    loadData();
    return () => {
      mounted = false;
    };
  }, [user]);

  const availablePublic = useMemo(() => {
    // Public listings for everyone; backend already filters private visibility for non-owners
    return configs.filter((cfg) => cfg.visibility !== 'private');
  }, [configs]);

  const privateAll = useMemo(() => {
    if (!user || user.role !== 'admin') return [];
    return configs.filter((cfg) => cfg.visibility === 'private');
  }, [configs, user]);

  const privateMine = useMemo(() => {
    if (!user) return [];
    // Admin: subset of all privadas; Enterprise: solo las suyas (backend ya limita visibilidad)
    return configs.filter(
      (cfg) => cfg.visibility === 'private' && cfg.created_by_user_id === user.id
    );
  }, [configs, user]);

  const [privateFilter, setPrivateFilter] = useState<'mine' | 'all' | number>('mine');

  const privateFiltered = useMemo(() => {
    if (!user || user.role !== 'admin') return privateMine;

    if (privateFilter === 'mine') {
      return privateMine;
    } else if (privateFilter === 'all') {
      return privateAll;
    } else {
      // Filter by specific user ID
      return configs.filter(
        (cfg) => cfg.visibility === 'private' && cfg.created_by_user_id === privateFilter
      );
    }
  }, [configs, user, privateFilter, privateMine, privateAll]);

  if (!user) return null;

  const handleToggleSubscription = (name: string) => {
    const isSubscribed = subscriptions.includes(name);
    setUpdating(true);
    const action = isSubscribed ? newsletterSubscriptionsApi.unsubscribe : newsletterSubscriptionsApi.subscribe;
    action(name)
      .then(() => {
        setSubscriptions((prev) =>
          isSubscribed ? prev.filter((item) => item !== name) : [...prev, name]
        );
      })
      .catch((err) => {
        console.error('No se pudo actualizar suscripción', err);
        setError('No pudimos actualizar tu suscripción. Intenta nuevamente.');
      })
      .finally(() => setUpdating(false));
  };

  const renderCard = (cfg: NewsletterConfig, variant: 'public' | 'private') => {
    const isSubscribed = subscriptions.includes(cfg.name);
    const badgeStyles =
      variant === 'private'
        ? 'bg-orange-100 text-orange-700 ring-1 ring-orange-200'
        : 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200';

    return (
      <div
        key={cfg.id}
        className="group rounded-2xl border border-gray-100 bg-white p-5 shadow-sm hover:-translate-y-0.5 hover:shadow-lg transition-all"
      >
        {/* Header: Badge + Status */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${badgeStyles}`}>
              {variant === 'private' ? <ShieldCheck className="w-4 h-4" /> : <Rss className="w-4 h-4" />}
              {variant === 'private' ? 'Privada' : 'Pública'}
            </span>
            {!cfg.is_active && (
              <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-full ring-1 ring-amber-100">
                Inactiva
              </span>
            )}
            {isSubscribed && (
              <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full ring-1 ring-green-100 flex items-center gap-1">
                <span className="inline-flex h-1.5 w-1.5 rounded-full bg-green-500"></span>
                Suscrito
              </span>
            )}
          </div>
        </div>

        {/* Title */}
        <div className="mb-2">
          <h3 className="text-lg font-bold text-transparent bg-clip-text bg-gradient-to-r from-gray-900 via-indigo-900 to-purple-900 leading-tight tracking-tight">
            {cfg.display_name || cfg.name}
          </h3>
        </div>

        {/* Description */}
        <p className="text-sm text-gray-600 mb-4 line-clamp-2">
          {cfg.description || 'Sin descripción disponible'}
        </p>

        {/* Metadata Row: Sources + Articles */}
        <div className="flex items-center gap-4 text-sm text-gray-600 mb-3">
          {cfg.source_count !== undefined && cfg.source_count > 0 && (
            <div className="flex items-center gap-1.5">
              <Rss className="w-4 h-4 text-indigo-500" />
              <span className="font-medium">
                {cfg.source_count} {cfg.source_count === 1 ? 'fuente' : 'fuentes'}
              </span>
            </div>
          )}
          {cfg.articles_count && (
            <div className="flex items-center gap-1.5">
              <BookOpen className="w-4 h-4 text-purple-500" />
              <span className="font-medium">
                {cfg.articles_count} artículos
              </span>
            </div>
          )}
        </div>

        {/* Category Icons */}
        {cfg.categories && cfg.categories.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap mb-4">
            {cfg.categories.map((category, idx) => (
              <CategoryBadge key={idx} category={category} />
            ))}
          </div>
        )}

        {/* Action Button */}
        <div className="pt-3 border-t border-gray-100">
          <button
            onClick={() => handleToggleSubscription(cfg.name)}
            disabled={updating}
            className={`w-full inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all ${
              isSubscribed
                ? 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                : 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md hover:shadow-lg group-hover:scale-[1.02]'
            } ${updating ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {isSubscribed ? 'Quitar suscripción' : 'Suscribirme'}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="text-sm text-gray-600">Descubre newsletters y gestiona tus suscripciones</p>
          <h1 className="text-2xl font-bold text-gray-900">Explorar newsletters</h1>
          <p className="text-sm text-gray-600">
            Suscríbete para que sus ediciones aparezcan en tu dashboard.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50"
        >
          <ArrowLeft className="w-4 h-4" />
          Volver al dashboard
        </Link>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-800">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <Sparkles className="w-6 h-6 text-indigo-500 animate-pulse" />
            <div className="space-y-2 flex-1">
              <div className="h-5 w-56 bg-gray-100 rounded animate-pulse" />
              <div className="h-3 w-72 bg-gray-100 rounded animate-pulse" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((key) => (
              <div key={key} className="h-80 bg-gray-50 border border-gray-100 rounded-2xl animate-pulse" />
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Combined Grid Layout - Shows both public and private newsletters side by side */}
          <div className={`grid grid-cols-1 gap-6 ${
            ((user.role === 'admin' && privateAll.length > 0) || (user.role === 'enterprise' && privateMine.length > 0))
              ? 'lg:grid-cols-2'
              : ''
          }`}>
            {/* Left Column: Public Newsletters */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Rss className="w-6 h-6 text-indigo-500" />
                <h2 className="text-xl font-bold text-gray-900">Newsletters públicas</h2>
                <span className="text-sm text-gray-500">({availablePublic.length})</span>
              </div>
              {availablePublic.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-gray-200 bg-gray-50 p-8 text-center">
                  <Rss className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-sm text-gray-600">No hay newsletters públicas disponibles por ahora.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {availablePublic.map((cfg) => renderCard(cfg, 'public'))}
                </div>
              )}
            </div>

            {/* Right Column: Private Newsletters */}
            {((user.role === 'admin' && privateAll.length > 0) || (user.role === 'enterprise' && privateMine.length > 0)) && (
              <div className="space-y-4 min-w-0">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <ShieldCheck className="w-6 h-6 text-orange-500 flex-shrink-0" />
                    <h2 className="text-xl font-bold text-gray-900">
                      {user.role === 'admin' ? 'Newsletters privadas' : 'Tus newsletters privadas'}
                    </h2>
                    <span className="text-sm text-gray-500">
                      ({user.role === 'admin' ? privateFiltered.length : privateMine.length})
                    </span>
                    {user.role === 'admin' && typeof privateFilter === 'number' && (
                      <span className="text-xs bg-purple-50 text-purple-700 px-2.5 py-1 rounded-full ring-1 ring-purple-200 flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5" />
                        {users.find((u) => u.id === privateFilter)?.nombre || 'Usuario'}
                      </span>
                    )}
                  </div>
                  {user.role === 'admin' && (
                    <div className="flex flex-col items-start sm:items-end gap-2 min-w-0 w-full sm:w-auto">
                      {/* Quick filters */}
                      <div className="flex items-center gap-2 text-xs flex-wrap">
                        <button
                          onClick={() => setPrivateFilter('mine')}
                          className={`rounded-lg px-2.5 py-1.5 font-semibold transition whitespace-nowrap ${
                            privateFilter === 'mine'
                              ? 'bg-orange-100 text-orange-800 ring-1 ring-orange-200'
                              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                          }`}
                        >
                          Mías
                        </button>
                        <button
                          onClick={() => setPrivateFilter('all')}
                          className={`rounded-lg px-2.5 py-1.5 font-semibold transition whitespace-nowrap ${
                            privateFilter === 'all'
                              ? 'bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200'
                              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                          }`}
                        >
                          Todas
                        </button>
                      </div>
                      {/* User selector */}
                      <div className="flex items-center gap-2 min-w-0 w-full sm:w-auto">
                        <User className="w-4 h-4 text-gray-500 flex-shrink-0" />
                        <select
                          value={typeof privateFilter === 'number' ? privateFilter : ''}
                          onChange={(e) => {
                            const value = e.target.value;
                            if (value === '') {
                              setPrivateFilter('all');
                            } else {
                              setPrivateFilter(parseInt(value, 10));
                            }
                          }}
                          className="text-xs rounded-lg border border-gray-200 px-2.5 py-1.5 bg-white text-gray-700 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition w-full sm:w-auto sm:max-w-[200px] md:max-w-[250px] truncate"
                        >
                          <option value="">Ver por usuario...</option>
                          {users.map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.nombre} ({u.email})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}
                </div>
                <div className="space-y-4">
                  {(user.role === 'admin' ? privateFiltered : privateMine).map((cfg) =>
                    renderCard(cfg, 'private')
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
