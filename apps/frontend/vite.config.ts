import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/work-file": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/status": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/view-script": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
