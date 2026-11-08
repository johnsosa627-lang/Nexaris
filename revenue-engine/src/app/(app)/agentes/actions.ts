"use server";

import { revalidatePath } from "next/cache";
import { centsFromForm, run, str, type ActionState } from "@/lib/action-state";
import { requireCtx } from "@/lib/session";
import { updateAgentSettings } from "@/server/agents";

export async function updateAgentAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await updateAgentSettings(ctx, str(form, "agentKey"), {
      enabled: form.get("enabled") === "on",
      model: str(form, "model") as never,
      monthlyBudgetCents: centsFromForm(form, "budget"),
      instructions: str(form, "instructions"),
    });
    revalidatePath("/agentes");
  }, "Configuración guardada.");
}
