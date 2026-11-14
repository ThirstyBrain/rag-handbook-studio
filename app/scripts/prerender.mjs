#!/usr/bin/env node
/**
 * Runs after `vite build`. Writes one static HTML file per route into dist/ so crawlers receive real
 * headings, text, links, canonicals and structured data without running JavaScript, then adds
 * 404.html, sitemap.xml, robots.txt and llms.txt.
 *
 * The page content comes from src/seo (loaded through Vite so aliases and ?raw imports work).
 * Site origin: SITE_URL, else Netlify's URL variable, else the default in src/seo/siteConfig.ts.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(root, "dist");

function log(level, message, extra = {}) {
  console[level === "error" ? "error" : "log"](JSON.stringify({ level, scope: "prerender", message, ...extra }));
}

/** Replaces the template's title and description with the page's head tags and fills #root. */
function inject(template, { head, body }) {
  const withoutDefaults = template.replace(/<title>[\s\S]*?<\/title>\s*/, "").replace(/<meta name="description"[^>]*>\s*/, "");
  if (!withoutDefaults.includes("</head>") || !withoutDefaults.includes('<div id="root"></div>')) {
    throw new Error('dist/index.html is missing "</head>" or <div id="root"></div>; the template changed.');
  }
  return withoutDefaults.replace("</head>", `    ${head}\n  </head>`).replace('<div id="root"></div>', `<div id="root">${body}</div>`);
}

function write(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content, "utf8");
}

async function main() {
  const templatePath = path.join(dist, "index.html");
  if (!fs.existsSync(templatePath)) throw new Error("dist/index.html not found. Run `vite build` first.");
  const template = fs.readFileSync(templatePath, "utf8");

  const server = await createServer({ root, configFile: path.join(root, "vite.config.ts"), server: { middlewareMode: true }, appType: "custom", logLevel: "warn" });
  try {
    const { DEFAULT_SITE_URL } = await server.ssrLoadModule("/src/seo/siteConfig.ts");
    const site = await server.ssrLoadModule("/src/seo/site.ts");
    const siteUrl = (process.env.SITE_URL || process.env.URL || DEFAULT_SITE_URL).replace(/\/+$/, "");
    const options = { siteUrl, hasOgImage: fs.existsSync(path.join(root, "public", "og-image.png")) };

    const pages = site.buildPages(options);
    for (const page of pages) {
      if (!page.body) throw new Error(`No static content for ${page.path}`);
      const file = page.path === "/" ? templatePath : path.join(dist, page.path, "index.html");
      write(file, inject(template, page));
    }
    write(path.join(dist, "404.html"), inject(template, site.buildNotFoundPage(options)));
    write(path.join(dist, "sitemap.xml"), site.buildSitemap(options));
    write(path.join(dist, "robots.txt"), site.buildRobots(options));
    write(path.join(dist, "llms.txt"), site.buildLlmsTxt(options));
    log("info", "prerendered", { pages: pages.length, siteUrl, ogImage: options.hasOgImage });
  } finally {
    await server.close();
  }
}

main().catch((error) => {
  log("error", "prerender failed", { error: String(error?.stack ?? error) });
  process.exit(1);
});
