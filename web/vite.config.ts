import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Vite 2 defaults to port 3000; pin 5173 so dev URL matches Vite 3+ / common expectations.
  server: { port: 5173 },
});
