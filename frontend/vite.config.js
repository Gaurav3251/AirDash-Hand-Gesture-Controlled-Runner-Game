import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on :5173 talking to the FastAPI backend on :8000 (see
// backend/api.py CORS config, and src/api.js for the base URL).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
