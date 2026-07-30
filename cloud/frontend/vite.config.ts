/// <reference types="node" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@webview/context-usage": path.resolve(
        rootDir,
        "../../editors/vscode/src/webview/context-usage.ts",
      ),
      "@webview/render": path.resolve(
        rootDir,
        "../../editors/vscode/src/webview/render.ts",
      ),
    },
  },
  server: {
    port: 5174,
    fs: {
      allow: [path.resolve(rootDir, "../..")],
    },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
      },
      "/events": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
      },
      "/command": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
      },
    },
  },
});
