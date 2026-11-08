import { beforeEach } from "vitest";

process.env.DATABASE_URL =
  process.env.TEST_DATABASE_URL ?? "postgres://postgres@127.0.0.1:5432/revenue_engine_test";
process.env.SETUP_TOKEN = "token-de-prueba";
process.env.ENCRYPTION_KEY = Buffer.alloc(32, 7).toString("base64");

const { getDb } = await import("@/db");
const { sql } = await import("drizzle-orm");

beforeEach(async () => {
  await getDb().execute(sql`
    truncate table audit_log, approvals, suppression_list, action_policies, agent_settings,
      follow_ups, activities, contacts, sessions, companies, users, workspaces restart identity cascade
  `);
});
