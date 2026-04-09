import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pipeline served under /zero-day/ when behind the portal gateway.

export default defineConfig({
  plugins: [react()],
  base: "/zero-day/",
  server: {
    host: "0.0.0.0",
    port: 5175,
  },
});
