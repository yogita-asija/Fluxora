import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Where the FastAPI app runs during `npm run dev` (outside Docker).
  const apiTarget = env.VITE_DEV_API_TARGET || "http://localhost:8000";

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        "/api": apiTarget,
        "/health": apiTarget,
      },
    },
  };
});
