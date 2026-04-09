import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config. Single React entry, no SSR, no fancy plugins.
// The dev server proxies /api to the backend at VITE_BACKEND_URL,
// which the components reference via import.meta.env.VITE_BACKEND_URL
// at runtime. The proxy is only used in dev (vite dev mode); the
// production build is static and the backend URL is baked in at
// build time.

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});
