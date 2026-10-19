/**
 * The shape a translation must have: the same nested keys as the English
 * source, every leaf a string. French files declare
 * `satisfies LocaleNamespace<typeof en>`, so a missing, extra, or misspelled
 * key is a type error rather than a silently untranslated string.
 */
export type LocaleNamespace<T> = {
  [K in keyof T]: T[K] extends string ? string : LocaleNamespace<T[K]>;
};
