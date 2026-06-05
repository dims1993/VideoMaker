import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // Generación masiva TTS (119+ bloques) puede tardar muchos minutos
        timeout: 3_600_000,
        proxyTimeout: 3_600_000,
      },
      "/work-file": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/status": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/view-script": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
