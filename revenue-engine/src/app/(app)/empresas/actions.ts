"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { dateFromLocalInput, run, str, type ActionState } from "@/lib/action-state";
import { requireCtx } from "@/lib/session";
import {
  addActivity,
  addContact,
  addFollowUp,
  changeStage,
  createCompany,
  optOutContact,
  setFollowUpStatus,
  updateCompany,
  type CompanyInput,
} from "@/server/crm";

function companyFromForm(form: FormData): CompanyInput {
  return {
    name: str(form, "name"),
    website: str(form, "website"),
    country: str(form, "country") || "UY",
    city: str(form, "city"),
    sector: str(form, "sector"),
    notes: str(form, "notes"),
  };
}

export async function createCompanyAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  let id = "";
  const result = await run(async () => {
    id = (await createCompany(ctx, companyFromForm(form))).id;
  });
  if (result?.ok) {
    revalidatePath("/empresas");
    redirect(`/empresas/${id}`);
  }
  return result;
}

function refresh(companyId: string) {
  revalidatePath(`/empresas/${companyId}`);
  revalidatePath("/empresas");
  revalidatePath("/");
}

export async function updateCompanyAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const id = str(form, "companyId");
  return run(async () => {
    await updateCompany(ctx, id, companyFromForm(form));
    refresh(id);
  }, "Datos actualizados.");
}

export async function changeStageAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const id = str(form, "companyId");
  return run(async () => {
    await changeStage(ctx, id, str(form, "stage"));
    refresh(id);
  }, "Etapa actualizada.");
}

export async function addContactAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const id = str(form, "companyId");
  return run(async () => {
    await addContact(ctx, id, {
      name: str(form, "name"),
      roleTitle: str(form, "roleTitle"),
      email: str(form, "email"),
      phone: str(form, "phone"),
      source: (str(form, "source") || null) as never,
      sourceUrl: str(form, "sourceUrl"),
    });
    refresh(id);
  }, "Contacto agregado.");
}

export async function optOutContactAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const companyId = str(form, "companyId");
  return run(async () => {
    await optOutContact(ctx, str(form, "contactId"));
    refresh(companyId);
  }, "Baja registrada. Su email quedó en la lista de exclusión.");
}

export async function addActivityAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const id = str(form, "companyId");
  return run(async () => {
    const when = str(form, "occurredAt");
    await addActivity(ctx, id, {
      type: str(form, "type"),
      title: str(form, "title"),
      body: str(form, "body"),
      contactId: str(form, "contactId"),
      occurredAt: when ? dateFromLocalInput(when) : undefined,
    });
    refresh(id);
  }, "Actividad registrada.");
}

export async function addFollowUpAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const id = str(form, "companyId");
  return run(async () => {
    await addFollowUp(ctx, id, {
      title: str(form, "title"),
      dueAt: dateFromLocalInput(str(form, "dueAt")),
      contactId: str(form, "contactId"),
    });
    refresh(id);
    revalidatePath("/seguimientos");
  }, "Seguimiento programado.");
}

export async function closeFollowUpAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const ctx = await requireCtx();
  const status = str(form, "status") === "cancelado" ? "cancelado" : "hecho";
  return run(async () => {
    const f = await setFollowUpStatus(ctx, str(form, "followUpId"), status);
    refresh(f.companyId);
    revalidatePath("/seguimientos");
  }, status === "hecho" ? "Marcado como hecho." : "Cancelado.");
}
