-- Categories Migration: Move from YAML to PostgreSQL
-- Created: 2025-12-03
-- Purpose: Full migration to database-managed categories

-- ============================================
-- CATEGORIES TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    consolidates JSONB DEFAULT '[]'::jsonb,  -- Array of predecessor category IDs
    examples JSONB DEFAULT '[]'::jsonb,       -- Array of example strings
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add index for fast lookups
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name);

-- ============================================
-- INITIAL DATA MIGRATION FROM categories.yml
-- ============================================

INSERT INTO categories (id, name, description, consolidates, examples) VALUES
(
    'politica',
    'politica',
    'politica nacional, gobierno, partidos politicos, justicia, educacion, legislacion',
    '["politica", "nacional", "justicia", "educacion"]'::jsonb,
    '["Gobierno anuncia reforma educativa", "Congreso aprueba nueva ley de presupuestos", "Tribunal Supremo dicta sentencia sobre caso de corrupción", "Ministro de Educación presenta plan nacional", "Elecciones regionales fijadas para mayo"]'::jsonb
),
(
    'economia',
    'economia',
    'macroeconomia, politica fiscal, bancos centrales, indicadores economicos, empleo, inflacion, pib, comercio internacional',
    '["economia"]'::jsonb,
    '["Banco Central sube tipos de interés al 4.5%", "Inflación anual se sitúa en el 3.2%", "PIB crece un 2.1% en el segundo trimestre", "Tasa de desempleo baja al 5.8%", "Gobierno anuncia recorte de impuestos corporativos"]'::jsonb
),
(
    'finanzas',
    'finanzas',
    'mercados financieros, bolsas, empresas, banca comercial, inversiones, fusiones, adquisiciones, energia, startups, resultados corporativos',
    '["empresas", "mercados", "energia"]'::jsonb,
    '["Bolsa cierra con caídas del 2% por volatilidad", "Goldman Sachs reporta ganancias récord en Q3", "Precio del petróleo alcanza máximos de $95 por barril", "Startup española recibe inversión de $50M", "Fusión entre dos gigantes tecnológicos valorada en $40B"]'::jsonb
),
(
    'tecnologia',
    'tecnologia',
    'tecnologia, ciencia, innovacion, salud, investigacion, medioambiente, sostenibilidad',
    '["tecnologia", "ciencia", "salud", "medioambiente"]'::jsonb,
    '["Nueva IA revoluciona diagnóstico médico", "Científicos descubren nueva especie en la Amazonía", "Estudio revela avances contra el Alzheimer", "Acuerdo climático fija objetivos de emisiones", "Apple presenta nuevo iPhone con chip revolucionario"]'::jsonb
),
(
    'geopolitica',
    'geopolitica',
    'relaciones internacionales, politica exterior, conflictos, diplomacia, organizaciones internacionales',
    '["internacional"]'::jsonb,
    '["Cumbre G7 acuerda sanciones contra país", "ONU advierte sobre crisis humanitaria", "Conflicto en Oriente Medio escala a nueva fase", "UE y China firman acuerdo comercial", "Presidente visita aliados europeos"]'::jsonb
),
(
    'sociedad',
    'sociedad',
    'lifestyle, cultura, moda, belleza, entretenimiento, arte, musica, cine, tv, celebrities, opinion, tendencias sociales',
    '["sociedad", "cultura", "entretenimiento", "opinion"]'::jsonb,
    '["Los anillos de compromiso más exclusivos de celebridades", "Festival de Cannes premia nueva película española", "Tendencias de moda para la próxima temporada", "Museo del Prado inaugura exposición de Velázquez", "Serie de Netflix rompe récords de audiencia", "Columna: Por qué necesitamos repensar la democracia"]'::jsonb
),
(
    'deportes',
    'deportes',
    'deportes, competiciones, atletas, equipos, resultados deportivos',
    '["deportes"]'::jsonb,
    '["Real Madrid vence al Barcelona 3-1", "Nadal anuncia su retirada del tenis profesional", "Juegos Olímpicos: España suma dos medallas de oro", "Liga de Campeones: resultados de cuartos de final", "Ciclista español gana etapa del Tour de Francia"]'::jsonb
),
(
    'otros',
    'otros',
    'contenido inclasificable, temas diversos que no encajan en las categorias principales',
    '[]'::jsonb,
    '["Artículos sobre temas muy específicos o nichos", "Contenido híbrido difícil de categorizar", "Noticias locales muy específicas sin relevancia nacional"]'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- ADD FOREIGN KEY TO URLS TABLE
-- ============================================

-- Add constraint to ensure categoria_tematica references valid categories
ALTER TABLE urls
ADD CONSTRAINT fk_urls_categoria_tematica
FOREIGN KEY (categoria_tematica) REFERENCES categories(id)
ON DELETE SET NULL;

-- ============================================
-- AUDIT: CATEGORY CHANGES TRACKING
-- ============================================

-- Track when categories are modified (for reclassification auditing)
CREATE TABLE IF NOT EXISTS category_changes (
    id SERIAL PRIMARY KEY,
    category_id TEXT NOT NULL,
    changed_by INTEGER REFERENCES users(id),  -- Admin who made the change
    change_type TEXT NOT NULL CHECK(change_type IN ('created', 'updated', 'deleted')),
    old_values JSONB,
    new_values JSONB,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_category_changes_category_id ON category_changes(category_id);
CREATE INDEX IF NOT EXISTS idx_category_changes_changed_at ON category_changes(changed_at);

-- ============================================
-- RECLASSIFICATION TRACKING
-- ============================================

-- Track reclassification jobs triggered by category modifications
CREATE TABLE IF NOT EXISTS reclassification_jobs (
    id SERIAL PRIMARY KEY,
    triggered_by INTEGER REFERENCES users(id),  -- Admin who triggered
    category_ids JSONB NOT NULL,  -- Array of categories that changed
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed')) DEFAULT 'pending',
    total_urls INTEGER DEFAULT 0,
    processed_urls INTEGER DEFAULT 0,
    failed_urls INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reclassification_jobs_status ON reclassification_jobs(status);
CREATE INDEX IF NOT EXISTS idx_reclassification_jobs_created_at ON reclassification_jobs(created_at);
