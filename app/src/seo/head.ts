import { ogFileName } from "./ogPath";
import type { PageMeta } from "./pageMeta";
import { OG_IMAGE_DIR } from "./siteConfig";

/**
 * Keeps <head> in step with the route after client-side navigation. The first load already has the
 * right tags (written at build time); this only updates them as the reader moves between pages.
 */
function setTag(selector: string, create: () => HTMLElement, attr: string, value: string): void {
  let el = document.head.querySelector<HTMLElement>(selector);
  if (!el) {
    el = create();
    document.head.appendChild(el);
  }
  el.setAttribute(attr, value);
}

const meta = (key: "name" | "property", name: string) => () => {
  const el = document.createElement("meta");
  el.setAttribute(key, name);
  return el;
};

export function applyPageMeta(page: PageMeta, origin: string): void {
  document.title = page.title;
  const url = `${origin}${page.path === "/" ? "/" : page.path}`;
  setTag('meta[name="description"]', meta("name", "description"), "content", page.description);
  setTag('meta[property="og:title"]', meta("property", "og:title"), "content", page.title);
  setTag('meta[property="og:description"]', meta("property", "og:description"), "content", page.description);
  setTag('meta[property="og:url"]', meta("property", "og:url"), "content", url);
  setTag('meta[property="og:type"]', meta("property", "og:type"), "content", page.ogType);
  if (!page.noindex) {
    const image = `${origin}${OG_IMAGE_DIR}/${ogFileName(page.path)}`;
    setTag('meta[property="og:image"]', meta("property", "og:image"), "content", image);
    setTag('meta[name="twitter:image"]', meta("name", "twitter:image"), "content", image);
  }
  setTag('meta[name="twitter:title"]', meta("name", "twitter:title"), "content", page.title);
  setTag('meta[name="twitter:description"]', meta("name", "twitter:description"), "content", page.description);

  const canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (page.noindex) canonical?.remove();
  else setTag('link[rel="canonical"]', () => Object.assign(document.createElement("link"), { rel: "canonical" }), "href", url);

  const robots = document.head.querySelector<HTMLMetaElement>('meta[name="robots"]');
  if (page.noindex) setTag('meta[name="robots"]', meta("name", "robots"), "content", "noindex");
  else robots?.remove();

  // Structured data describes the page that was prerendered; drop it when the reader navigates away from that page.
  document.head.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
    if (s.getAttribute("data-path") !== page.path) s.remove();
  });
}
