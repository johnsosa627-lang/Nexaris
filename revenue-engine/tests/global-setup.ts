import { execFileSync } from "node:child_process";
import path from "node:path";

/** Antes de todas las pruebas: deja la base de pruebas con el esquema al día. */
export default function setup() {
  const url = process.env.TEST_DATABASE_URL ?? "postgres://postgres@127.0.0.1:5432/revenue_engine_test";
  if (!/test/.test(url)) {
    throw new Error("Por seguridad, TEST_DATABASE_URL tiene que apuntar a una base cuyo nombre contenga 'test'.");
  }
  process.env.DATABASE_URL = url;
  execFileSync("node", [path.join(__dirname, "..", "scripts", "migrate.mjs")], {
    env: { ...process.env, DATABASE_URL: url },
    stdio: "inherit",
  });
}
