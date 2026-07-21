-- =============================================================================
-- Migration: Habilitar RLS en todas las tablas del proyecto Darius AI
-- Fecha: 2026-07-20
-- Motivo: Supabase reportó tablas públicas sin Row-Level Security
--         (issue: rls_disabled_in_public)
-- =============================================================================
-- Cómo aplicar:
--   1. Ve a https://supabase.com/dashboard/project/lsuduiwbjkmcxhidlsvj/sql
--   2. Pega todo este archivo
--   3. Ejecútalo
-- =============================================================================

-- ── chat_history ─────────────────────────────────────────────────────────────
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_insert_chat_history"
    ON chat_history FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "anon_select_chat_history"
    ON chat_history FOR SELECT
    TO anon
    USING (true);

-- ── config ───────────────────────────────────────────────────────────────────
ALTER TABLE config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_config"
    ON config FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "anon_insert_config"
    ON config FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "anon_update_config"
    ON config FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

-- ── apps_cache ───────────────────────────────────────────────────────────────
ALTER TABLE apps_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_apps_cache"
    ON apps_cache FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "anon_insert_apps_cache"
    ON apps_cache FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "anon_update_apps_cache"
    ON apps_cache FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

-- ── apps_cache_meta ──────────────────────────────────────────────────────────
ALTER TABLE apps_cache_meta ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_apps_cache_meta"
    ON apps_cache_meta FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "anon_insert_apps_cache_meta"
    ON apps_cache_meta FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "anon_update_apps_cache_meta"
    ON apps_cache_meta FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);
