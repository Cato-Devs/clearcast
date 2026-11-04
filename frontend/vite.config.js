import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // For "npm run dev": send API calls to the backend started by Docker Compose
  server: { proxy: { "/api": "http://localhost:8000" } },
});
