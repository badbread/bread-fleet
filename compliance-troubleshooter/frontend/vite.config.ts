import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Troubleshooter served under /compliance/ when behind the portal
// gateway. The base path ensures asset URLs resolve correctly. The
// frontend's api.ts uses import.meta.env.BASE_URL to prefix API
// calls so they route through the portal's /compliance/api/ proxy.

export default defineConfig({
  plugins: [react()],
  base: "/compliance/",
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});
