export const MAX_TAGS = 20;
export const MAX_TAG_LENGTH = 32;

/** `tags` plus `raw` (trimmed), unless it's empty, a duplicate (ignoring case) or the list is full. */
export function addTag(tags: string[], raw: string): string[] {
  const tag = raw.trim().slice(0, MAX_TAG_LENGTH);
  if (!tag || tags.length >= MAX_TAGS || tags.some((existing) => existing.toLowerCase() === tag.toLowerCase())) return tags;
  return [...tags, tag];
}
