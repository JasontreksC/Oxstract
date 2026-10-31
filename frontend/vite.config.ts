import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_PROXY || "http://127.0.0.1:8000";
  // IP 주소는 늘 허용된다. oxstract.lan 같은 이름으로 열 때만 VITE_ALLOWED_HOSTS에 적는다.
  const allowedHosts = (env.VITE_ALLOWED_HOSTS || "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);
  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      allowedHosts,
      proxy: {
        "/api": target,
      },
    },
  };
});
