import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@webview": path.resolve(__dirname, "../vscode/src/webview"),
      "dompurify": path.resolve(__dirname, "node_modules/dompurify/dist/purify.es.mjs"),
      "marked": path.resolve(__dirname, "node_modules/marked/lib/marked.esm.js"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/command": "http://127.0.0.1:8848",
      "/events": "http://127.0.0.1:8848",
      "/api": "http://127.0.0.1:8848",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
  },
});
