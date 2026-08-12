const DATE_SUFFIX = /-\d{4}-\d{2}-\d{2}$/;
const UNDERSCORE_VERSION = /(gpt-\d+)_(\d+)/g;

export const DEFAULT_OPENAI_MODEL = "gpt-5.4-mini";

// Free-tier mini models (2.5 million tokens/day)
export const MINI_TIER_MODELS = [
  "gpt-5.4-mini",
  "gpt-5.4-nano",
  "gpt-5.1-codex-mini",
  "gpt-5-mini",
  "gpt-5-nano",
  "gpt-4.1-mini",
  "gpt-4.1-nano",
  "gpt-4o-mini",
  "o1-mini",
  "o3-mini",
  "o4-mini",
  "codex-mini-latest",
] as const;

// Free-tier standard models (250 thousand tokens/day)
export const STANDARD_TIER_MODELS = [
  "gpt-5.4",
  "gpt-5.2",
  "gpt-5.1",
  "gpt-5.1-codex",
  "gpt-5",
  "gpt-5-codex",
  "gpt-5-chat-latest",
  "gpt-4.1",
  "gpt-4o",
  "o1",
  "o3",
] as const;

export const ALLOWED_OPENAI_MODELS = [...MINI_TIER_MODELS, ...STANDARD_TIER_MODELS] as const;
export type AllowedOpenAIModel = (typeof ALLOWED_OPENAI_MODELS)[number];

/**
 * Normalize any model name variant to its clean base alias.
 * - gpt-5_4-mini-2026-03-17  →  gpt-5.4-mini
 * - gpt-4_1-mini             →  gpt-4.1-mini
 */
export function canonicalizeOpenAIModel(model?: string | null): string {
  const normalized = (model || "").trim();
  if (!normalized) return DEFAULT_OPENAI_MODEL;
  return normalized
    .replace(UNDERSCORE_VERSION, "$1.$2")
    .replace(DATE_SUFFIX, "");
}

export function isAllowedOpenAIModel(model?: string | null): boolean {
  return (ALLOWED_OPENAI_MODELS as readonly string[]).includes(canonicalizeOpenAIModel(model));
}

export function coerceOpenAIModel(model?: string | null): string {
  const normalized = canonicalizeOpenAIModel(model);
  return isAllowedOpenAIModel(normalized) ? normalized : DEFAULT_OPENAI_MODEL;
}

export function normalizeOpenAIModel(model?: string | null): string {
  return coerceOpenAIModel(model);
}
