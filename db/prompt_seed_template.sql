-- Seed template for prompt management (fill with real values before applying)
-- This file is a scaffold to insert baseline data into the prompt management tables.
-- Replace placeholders and extend as needed. Do NOT run as-is without reviewing.

-- Example models (align with your env defaults)
INSERT INTO models (alias, provider, model_name, purpose, max_tokens)
VALUES
    ('MODEL_URL_FILTER', 'openai', 'gpt-4o-mini', 'url_filter', 16000),
    ('MODEL_CLASSIFIER', 'openai', 'gpt-4o-mini', 'classifier', 16000),
    ('MODEL_RANKER', 'openai', 'gpt-4o-mini', 'ranker', 16000),
    ('MODEL_COMPLETENESS_VALIDATOR', 'openai', 'gpt-4o-mini', 'completeness', 16000),
    ('MODEL_PAYWALL_VALIDATOR', 'openai', 'gpt-4o-mini', 'paywall', 16000)
ON CONFLICT (alias) DO NOTHING;

-- Example prompt categories (replace <JSON> with actual categories from config/categories.yml)
-- INSERT INTO prompt_categories (name, items, notes)
-- VALUES ('thematic_categories', '<JSON>', 'Imported from config/categories.yml')
-- ON CONFLICT (name) DO NOTHING;

-- Example llm_prompts rows (replace prompts/system/user templates with actual text)
-- INSERT INTO llm_prompts (name, stage, operation, scope, system_prompt, user_prompt_template, response_format, default_model, temperature, max_tokens, batch_size, status, notes)
-- VALUES
--   ('filter_news_urls', '01', 'filter_news_urls', 'composite', '<system_prompt>', '<user_prompt_template>', '{"type":"json_object","schema":"classifications"}', 'MODEL_URL_FILTER', 0.2, 2000, 50, 'approved', 'Imported v1'),
--   ('filter_content_urls', '01', 'filter_content_urls', 'composite', '<system_prompt>', '<user_prompt_template>', '{"type":"json_object","schema":"classifications"}', 'MODEL_URL_FILTER', 0.2, 2000, 50, 'approved', 'Imported v1');

-- Example newsletter templates (Stage 05)
-- INSERT INTO newsletter_templates (name, description, system_prompt, user_prompt_template, placeholders, default_model, temperature, max_tokens, status, notes)
-- VALUES
--   ('default', 'Default newsletter template', '<system_prompt>', '<user_prompt_template>', '["date","newsletter_name","context"]', 'gpt-4o-mini', 0.3, 4000, 'approved', 'Imported v1')
-- ON CONFLICT (name) DO NOTHING;

-- Map Stage→Operation to prompts (fill prompt_id via subquery by name)
-- INSERT INTO prompt_usages (stage, operation, prompt_id, enabled)
-- VALUES
--   ('01', 'filter_news_urls', (SELECT id FROM llm_prompts WHERE name='filter_news_urls'), TRUE)
-- ON CONFLICT (stage, operation) DO NOTHING;
