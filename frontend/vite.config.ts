import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      // ws proxy only enabled when VITE_WS_PROXY=true (i.e. local dev with backend)
      ...(process.env.VITE_WS_PROXY
        ? { "/ws": { target: "ws://localhost:8000", ws: true } }
        : {}),
    },
  },
});
