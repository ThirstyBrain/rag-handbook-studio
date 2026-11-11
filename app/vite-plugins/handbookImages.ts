import fs from "node:fs";
import path from "node:path";
import type { Plugin } from "vite";

/**
 * Chapters embed figures as `../assets/images/...`, which the browser resolves to `/assets/images/...`.
 * The handbook's text is bundled, but its image files are not, so this plugin publishes them at that URL:
 * served from the handbook folder in dev, copied into the output folder on build. The handbook is only read.
 */
const URL_PREFIX = "/assets/images/";

const CONTENT_TYPES: Record<string, string> = {
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
};

export function handbookImages(handbookDir: string): Plugin {
  const imagesDir = path.join(handbookDir, "docs", "assets", "images");
  let outDir = "";

  return {
    name: "handbook-images",
    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir);
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = decodeURIComponent((req.url ?? "").split("?")[0] ?? "");
        if (!url.startsWith(URL_PREFIX)) return next();
        const file = path.normalize(path.join(imagesDir, url.slice(URL_PREFIX.length)));
        const contentType = CONTENT_TYPES[path.extname(file).toLowerCase()];
        // Reject path traversal and unknown types; anything missing falls through to the app.
        if (!file.startsWith(imagesDir + path.sep) || !contentType || !fs.existsSync(file)) return next();
        res.setHeader("Content-Type", contentType);
        fs.createReadStream(file).pipe(res);
      });
    },
    closeBundle() {
      if (!fs.existsSync(imagesDir)) {
        this.warn(`handbook-images: ${imagesDir} not found, figures will not display`);
        return;
      }
      fs.cpSync(imagesDir, path.join(outDir, URL_PREFIX), { recursive: true });
    },
  };
}
