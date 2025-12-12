-- ============================================================================
-- Sources Migration: Migrar sources.yml a PostgreSQL
-- ============================================================================
-- Este script crea la tabla 'sources' y migra los datos existentes de YAML

-- Tabla: sources
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,  -- ID único (ej: 'elconfidencial')
    display_name VARCHAR(255) NOT NULL,  -- Nombre mostrado (ej: 'El Confidencial')
    base_url TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'es',  -- es, en, fr
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 1,  -- 1=máxima prioridad
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(is_active);
CREATE INDEX IF NOT EXISTS idx_sources_priority ON sources(priority DESC);
CREATE INDEX IF NOT EXISTS idx_sources_language ON sources(language);

-- Función para updated_at automático (si no existe)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para updated_at automático
CREATE TRIGGER update_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Migración de datos desde sources.yml
-- ============================================================================

-- Fuentes Españolas (sin campo notes en el INSERT)
INSERT INTO sources (name, display_name, base_url, language, description, is_active, priority, notes) VALUES
('elconfidencial', 'El Confidencial', 'https://www.elconfidencial.com/', 'es',
 'Medio español generalista con enfoque en economía y política', true, 1, NULL),

('elpais', 'El País', 'https://elpais.com/', 'es',
 'Principal diario español, cobertura generalista', true, 1, NULL),

('elmundo', 'El Mundo', 'https://www.elmundo.es/', 'es',
 'Diario español generalista', true, 1, NULL),

('expansion', 'Expansión', 'https://www.expansion.com/', 'es',
 'Diario económico español', true, 1, NULL),

('abc', 'ABC', 'https://www.abc.es/', 'es',
 'Diario español generalista', true, 1, NULL),

-- Fuentes Internacionales
('ft', 'Financial Times', 'https://www.ft.com/', 'en',
 'Medio económico y business británico, referencia mundial', true, 1, NULL),

('bloomberg', 'Bloomberg', 'https://www.bloomberg.com/', 'en',
 'Medio líder en noticias financieras, mercados y análisis económico', false, 1, 'DESACTIVADO: paywall agresivo, solo extrae 3 links de suscripción'),

('nyt', 'The New York Times', 'https://www.nytimes.com/', 'en',
 'Principal diario estadounidense, cobertura global', true, 1, NULL),

('bbc', 'BBC News', 'https://www.bbc.com/news', 'en',
 'Medio público británico, cobertura internacional de referencia', true, 1, NULL),

('lemonde', 'Le Monde', 'https://www.lemonde.fr/', 'fr',
 'Principal diario francés, cobertura internacional', true, 1, NULL)

ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- Verificación
-- ============================================================================

-- Mostrar count de sources migradas
DO $$
DECLARE
    source_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO source_count FROM sources;
    RAISE NOTICE 'Sources migradas: %', source_count;
END $$;
