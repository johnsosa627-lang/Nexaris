"use server";

import { revalidatePath } from "next/cache";
import { centsFromForm, run, str, type ActionState } from "@/lib/action-state";
import { requireCtx } from "@/lib/session";
import { clearDemoData, loadDemoData } from "@/server/demo";
import {
  addSuppression,
  pauseAutomations,
  removeSuppression,
  resumeAutomations,
  setPolicyLevel,
  updateLimits,
} from "@/server/security";

function refreshAll() {
  revalidatePath("/", "layout");
}

export async function pauseAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await pauseAutomations(ctx, str(form, "reason"));
    refreshAll();
  }, "Automatizaciones detenidas.");
}

export async function resumeAction(): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await resumeAutomations(ctx);
    refreshAll();
  }, "Automatizaciones reanudadas.");
}

export async function limitsAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    const dailyEmailLimit = Number(str(form, "dailyEmailLimit"));
    await updateLimits(ctx, {
      aiMonthlyBudgetCents: centsFromForm(form, "aiMonthlyBudget"),
      maxSpendPerActionCents: centsFromForm(form, "maxSpendPerAction"),
      dailyEmailLimit: Number.isFinite(dailyEmailLimit) ? Math.trunc(dailyEmailLimit) : -1,
    });
    revalidatePath("/seguridad");
  }, "Límites guardados.");
}

export async function policyAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await setPolicyLevel(ctx, str(form, "actionType"), Number(str(form, "level")));
    revalidatePath("/seguridad");
    revalidatePath("/agentes");
  }, "Nivel actualizado.");
}

export async function addSuppressionAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await addSuppression(ctx, str(form, "value"), str(form, "reason"));
    revalidatePath("/seguridad");
  }, "Agregado a la lista de exclusión.");
}

export async function removeSuppressionAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await removeSuppression(ctx, str(form, "id"));
    revalidatePath("/seguridad");
  }, "Quitado de la lista.");
}

export async function loadDemoAction(): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await loadDemoData(ctx);
    refreshAll();
  }, "Datos de prueba cargados. Están marcados como PRUEBA.");
}

export async function clearDemoAction(): Promise<ActionState> {
  const ctx = await requireCtx();
  return run(async () => {
    await clearDemoData(ctx);
    refreshAll();
  }, "Datos de prueba borrados. Tus datos reales no se tocaron.");
}
