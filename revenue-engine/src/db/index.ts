import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

function createClient() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("Falta la variable de entorno DATABASE_URL (dirección de la base de datos).");
  }
  const client = postgres(url, { max: Number(process.env.DATABASE_POOL_MAX ?? 10) });
  return drizzle(client, { schema });
}

type Db = ReturnType<typeof createClient>;

// En desarrollo Next.js recarga módulos: reutilizamos la conexión para no abrir cientos.
const globalForDb = globalThis as unknown as { __reDb?: Db };

export function getDb(): Db {
  if (!globalForDb.__reDb) globalForDb.__reDb = createClient();
  return globalForDb.__reDb;
}

export type { Db };
export { schema };
