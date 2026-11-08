import { getDb } from "@/db";
import { users, workspaces } from "@/db/schema";
import type { Role } from "@/lib/catalog";
import type { Ctx } from "@/server/context";
import { hashPassword } from "@/server/password";

/** Crea un espacio de trabajo con un usuario y devuelve su contexto. */
export async function makeWorkspace(name = "Agencia de prueba", role: Role = "owner"): Promise<Ctx> {
  const db = getDb();
  const [ws] = await db.insert(workspaces).values({ name }).returning();
  const ctx = await addUser(ws.id, role);
  return ctx;
}

let counter = 0;
export async function addUser(workspaceId: string, role: Role, password = "clave-segura-123"): Promise<Ctx & { email: string }> {
  counter += 1;
  const email = `u${counter}-${Date.now()}@prueba.test`;
  const [u] = await getDb()
    .insert(users)
    .values({ workspaceId, email, name: `Usuario ${counter}`, passwordHash: await hashPassword(password), role })
    .returning();
  return { userId: u.id, workspaceId, role, companyId: null, email };
}
