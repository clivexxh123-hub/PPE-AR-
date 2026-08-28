import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget =
    env.VITE_API_PROXY_TARGET || "http://127.0.0.1:9530";
  const resourceTarget =
    env.VITE_RESOURCE_API_PROXY_TARGET ||
    "http://127.0.0.1:9530";

  return {
    plugins: [vue()],

    server: {
      host: "0.0.0.0",
      port: 9531,

      proxy: {
        "/api/models": {
          target: resourceTarget,
          changeOrigin: true
        },

        "/api/scenes": {
          target: resourceTarget,
          changeOrigin: true
        },

        "/uploads/generation-demo": {
          target: resourceTarget,
          changeOrigin: true
        },

        "/uploads/models": {
          target: resourceTarget,
          changeOrigin: true
        },

        "/uploads/scenes": {
          target: resourceTarget,
          changeOrigin: true
        },

        "/api": {
          target: apiTarget,
          changeOrigin: true
        },

        "/uploads": {
          target: apiTarget,
          changeOrigin: true
        }
      }
    }
  };
});
