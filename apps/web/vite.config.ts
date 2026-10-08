import { defineConfig } from "vite";

const apiProxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

const outDir = process.env.LOTO_DIST_DIR || "dist";

export default defineConfig({
  server: {
    port: 5173,
    proxy: apiProxy,
  },
  preview: {
    port: 4173,
    proxy: apiProxy,
  },
  build: {
    outDir,
    emptyOutDir: true,
  },
  appType: "spa",
});
