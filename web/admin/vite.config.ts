import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server for the admin dashboard.
// /admin/* requests are proxied to the Flask backend so the app can call the
// API same-origin (no CORS involved in development).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/admin": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
