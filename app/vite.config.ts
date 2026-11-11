import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(fileURLToPath(import.meta.url));
/** The handbook repository is the single source of truth. It is read, never written. */
export const HANDBOOK_DIR = path.resolve(root, "../handbook");

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(root, "src"),
      "@handbook": HANDBOOK_DIR,
    },
  },
  server: { port: 5180, fs: { allow: [root, HANDBOOK_DIR] } },
  preview: { port: 5181 },
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // The handbook text changes far more often than the app code, so it is cached on its own.
        manualChunks(id) {
          if (id.startsWith(HANDBOOK_DIR.replace(/\\/g, "/")) || id.includes("/src/generated/")) return "handbook-content";
          if (/node_modules\/(react|react-dom|scheduler|marked|dompurify)\//.test(id)) return "vendor";
          return undefined;
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    css: false,
  },
});
