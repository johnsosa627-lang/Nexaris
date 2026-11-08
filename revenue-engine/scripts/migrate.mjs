// Aplica las migraciones pendientes de la base de datos. Se ejecuta solo al iniciar el servidor.
import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import postgres from "postgres";
import path from "node:path";
import { fileURLToPath } from "node:url";

const url = process.env.DATABASE_URL;
if (!url) {
  console.error("Falta DATABASE_URL");
  process.exit(1);
}
const here = path.dirname(fileURLToPath(import.meta.url));
const client = postgres(url, { max: 1, onnotice: () => {} });
try {
  await migrate(drizzle(client), { migrationsFolder: path.join(here, "..", "drizzle") });
  console.log("Base de datos al día.");
} finally {
  await client.end();
}
