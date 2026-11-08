import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      // "server-only" impide usar el código en el navegador; en las pruebas no aplica.
      "server-only": path.resolve(__dirname, "tests/server-only-stub.ts"),
    },
  },
  test: {
    environment: "node",
    globalSetup: ["tests/global-setup.ts"],
    setupFiles: ["tests/setup.ts"],
    // Las pruebas comparten una base de datos: se corren de a una para no pisarse.
    fileParallelism: false,
    include: ["tests/**/*.test.ts"],
  },
});
