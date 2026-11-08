"use server";

import { revalidatePath } from "next/cache";
import { run, str, type ActionState } from "@/lib/action-state";
import { requireCtx } from "@/lib/session";
import { decideApproval } from "@/server/gateway";
// Registra el ejecutor de "preparar_diagnostico" (encola el análisis al aprobarse).
import "@/server/diagnosis";
import { kickWorker } from "@/server/worker";

export async function decideAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const decision = str(form, "decision") === "aprobar" ? "aprobar" : "rechazar";
  return run(async () => {
    const r = await decideApproval(ctx, {
      approvalId: str(form, "approvalId"),
      decision,
      note: str(form, "note"),
      confirmation: str(form, "confirmation"),
    });
    kickWorker();
    revalidatePath("/aprobaciones");
    revalidatePath("/");
    const nota = (r?.result as { nota?: string } | null)?.nota;
    return decision === "rechazar" ? "Rechazada." : (nota ?? "Aprobada.");
  });
}
