import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],

  server: {
    host: "0.0.0.0",
    port: 9531,

    proxy: {
      "/api": {
        target: "http://127.0.0.1:9530",
        changeOrigin: true
      },

      "/uploads": {
        target: "http://127.0.0.1:9530",
        changeOrigin: true
      }
    }
  }
});
