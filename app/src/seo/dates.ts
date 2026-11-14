/** Publication and last-modified dates (ISO) per handbook source file, injected at build time from git. */
export interface ContentDates {
  published: string;
  modified: string;
}

declare const __CONTENT_DATES__: Record<string, ContentDates> | undefined;

/** `sourcePath` is repo-relative to the handbook, e.g. "docs/chapters/09-hybrid-search.md". */
export function contentDates(sourcePath: string): ContentDates | undefined {
  return typeof __CONTENT_DATES__ === "undefined" ? undefined : __CONTENT_DATES__[sourcePath];
}

export function latestModified(): string | undefined {
  if (typeof __CONTENT_DATES__ === "undefined") return undefined;
  return Object.values(__CONTENT_DATES__)
    .map((d) => d.modified)
    .sort()
    .pop();
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}
