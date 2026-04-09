import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dashboard served under /dashboard/ when behind the portal gateway.
// The base path ensures asset URLs resolve correctly regardless of
// whether the app is accessed standalone or through the portal.

export default defineConfig({
  plugins: [react()],
  base: "/dashboard/",
  server: {
    host: "0.0.0.0",
    port: 5174,
  },
});
