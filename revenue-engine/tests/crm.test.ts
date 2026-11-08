import { describe, expect, it } from "vitest";
import { makeWorkspace } from "./helpers";
import {
  addActivity,
  addContact,
  addFollowUp,
  changeStage,
  createCompany,
  getCompanyDetail,
  getDashboard,
  listCompanies,
  listFollowUps,
  optOutContact,
  setFollowUpStatus,
  updateCompany,
} from "@/server/crm";
import { clearDemoData, loadDemoData } from "@/server/demo";
import { addSuppression, isSuppressed, listAudit } from "@/server/security";
import { domainFromUrl } from "@/lib/format";
import { listAgents, updateAgentSettings } from "@/server/agents";

describe("empresas", () => {
  it("normaliza el sitio web y evita duplicados por dominio", async () => {
    const ctx = await makeWorkspace();
    const c = await createCompany(ctx, { name: "Autos Uno", website: "www.AutosUno.com.uy/contacto" });
    expect(c.website).toBe("https://www.AutosUno.com.uy/contacto");
    expect(c.domain).toBe("autosuno.com.uy");
    await expect(createCompany(ctx, { name: "Otra", website: "https://autosuno.com.uy" })).rejects.toThrow(/Ya existe/);
  });

  it("rechaza sitios web inválidos", async () => {
    const ctx = await makeWorkspace();
    await expect(createCompany(ctx, { name: "Empresa X", website: "no es una web" })).rejects.toThrow(/no es válida/);
  });

  it("los datos de un espacio de trabajo no se ven desde otro", async () => {
    const a = await makeWorkspace("A");
    const b = await makeWorkspace("B");
    const c = await createCompany(a, { name: "Solo de A" });
    expect(await listCompanies(b)).toHaveLength(0);
    await expect(getCompanyDetail(b, c.id)).rejects.toThrow(/no encontrada/);
    await expect(changeStage(b, c.id, "cliente")).rejects.toThrow(/no encontrada/);
    await expect(addContact(b, c.id, { name: "Intruso" })).rejects.toThrow(/no encontrada/);
  });

  it("guarda el historial de cambios al editar", async () => {
    const ctx = await makeWorkspace();
    const c = await createCompany(ctx, { name: "Inmo", city: "Montevideo" });
    await updateCompany(ctx, c.id, { name: "Inmo", city: "Salto" });
    const log = await listAudit(ctx);
    const edit = log.find((l) => l.action === "empresa.editada");
    expect(edit?.details).toMatchObject({ cambios: { city: { antes: "Montevideo", despues: "Salto" } } });
  });

  it("el cambio de etapa queda en la actividad de la empresa", async () => {
    const ctx = await makeWorkspace();
    const c = await createCompany(ctx, { name: "Tienda" });
    await changeStage(ctx, c.id, "contactado");
    const d = await getCompanyDetail(ctx, c.id);
    expect(d.company.stage).toBe("contactado");
    expect(d.activities[0].title).toBe("Etapa: Nuevo → Contactado");
    await expect(changeStage(ctx, c.id, "inventada")).rejects.toThrow(/desconocida/);
  });

  it("busca por nombre, ciudad o sector", async () => {
    const ctx = await makeWorkspace();
    await createCompany(ctx, { name: "Automotora Sur", city: "Montevideo", sector: "Automotoras" });
    await createCompany(ctx, { name: "Inmobiliaria Norte", city: "Salto" });
    expect(await listCompanies(ctx, { q: "salto" })).toHaveLength(1);
    expect(await listCompanies(ctx, { q: "automot" })).toHaveLength(1);
    expect(await listCompanies(ctx, { q: "%" })).toHaveLength(0);
  });
});

describe("contactos", () => {
  it("exige indicar el origen si hay email o teléfono", async () => {
    const ctx = await makeWorkspace();
    const c = await createCompany(ctx, { name: "Empresa" });
    await expect(addContact(ctx, c.id, { name: "Ana", email: "ana@empresa.com" })).rejects.toThrow(/de dónde salió/);
    const ok = await addContact(ctx, c.id, {
      name: "Ana",
      email: "Ana@Empresa.com",
      source: "sitio_web_empresa",
      sourceUrl: "https://empresa.com/contacto",
    });
    expect(ok.email).toBe("ana@empresa.com");
    // Sin email ni teléfono no hace falta origen
    await addContact(ctx, c.id, { name: "Pedro (gerente)" });
  });

  it("la baja agrega el email a la lista de exclusión", async () => {
    const ctx = await makeWorkspace();
    const c = await createCompany(ctx, { name: "Empresa" });
    const ct = await addContact(ctx, c.id, { name: "Ana", email: "ana@empresa.com", source: "el_contacto_lo_dio" });
    await optOutContact(ctx, ct.id);
    expect(await isSuppressed(ctx.workspaceId, "ana@empresa.com")).toBe(true);
    const d = await getCompanyDetail(ctx, c.id);
    expect(d.contacts[0].suppressed).toBe(true);
  });

  it("la exclusión por dominio cubre todos sus emails y subdominios", async () => {
    const ctx = await makeWorkspace();
    await addSuppression(ctx, "@empresa.com", "Pidió no ser contactada");
    expect(await isSuppressed(ctx.workspaceId, "cualquiera@empresa.com")).toBe(true);
    expect(await isSuppressed(ctx.workspaceId, "x@ventas.empresa.com")).toBe(true);
    expect(await isSuppressed(ctx.workspaceId, "x@otraempresa.com")).toBe(false);
  });
});

describe("actividad y seguimientos", () => {
  it("no permite registrar actividades en el futuro", async () => {
    const ctx = await makeWorkspace();
    const c = await createCompany(ctx, { name: "Empresa E" });
    await expect(
      addActivity(ctx, c.id, { type: "llamada", title: "Llamada", occurredAt: new Date(Date.now() + 86400_000) }),
    ).rejects.toThrow(/futura/);
    await expect(addActivity(ctx, c.id, { type: "cambio_etapa", title: "trampa" })).rejects.toThrow();
  });

  it("crea, lista y cierra seguimientos", async () => {
    const ctx = await makeWorkspace();
    const c = await createCompany(ctx, { name: "Empresa E" });
    const f = await addFollowUp(ctx, c.id, { title: "Llamar", dueAt: new Date(Date.now() - 3600_000) });
    expect(await listFollowUps(ctx)).toHaveLength(1);
    const dash = await getDashboard(ctx);
    expect(dash.overdueFollowUps).toBe(1);
    await setFollowUpStatus(ctx, f.id, "hecho");
    expect(await listFollowUps(ctx)).toHaveLength(0);
    await expect(setFollowUpStatus(ctx, f.id, "hecho")).rejects.toThrow(/ya estaba cerrado/);
  });
});

describe("panel y datos de prueba", () => {
  it("el panel cuenta por etapa y avisa de los datos de prueba; se pueden borrar", async () => {
    const ctx = await makeWorkspace();
    await loadDemoData(ctx);
    await expect(loadDemoData(ctx)).rejects.toThrow(/ya están cargados/);
    const dash = await getDashboard(ctx);
    expect(dash.totalCompanies).toBe(5);
    expect(dash.activeClients).toBe(1);
    expect(dash.openOpportunities).toBe(2);
    expect(dash.pendingApprovals).toBe(1);
    expect(dash.alerts.some((a) => a.text.includes("prueba"))).toBe(true);

    const real = await createCompany(ctx, { name: "Empresa real" });
    await clearDemoData(ctx);
    const after = await listCompanies(ctx);
    expect(after.map((c) => c.id)).toEqual([real.id]);
    expect((await getDashboard(ctx)).pendingApprovals).toBe(0);
  });
});

describe("agentes", () => {
  it("lista los 13 agentes y no deja encender uno que todavía no está construido", async () => {
    const ctx = await makeWorkspace();
    const agents = await listAgents(ctx);
    expect(agents).toHaveLength(13);
    expect(agents.every((a) => !a.enabled)).toBe(true);
    await expect(
      updateAgentSettings(ctx, "seo_engine", { enabled: true, model: "claude-opus-5-5", monthlyBudgetCents: 0, instructions: "" }),
    ).rejects.toThrow(/todavía no está construido/);
    await updateAgentSettings(ctx, "director", {
      enabled: false,
      model: "claude-sonnet-5-5",
      monthlyBudgetCents: 1500,
      instructions: "Priorizar automotoras",
    });
    const director = (await listAgents(ctx)).find((a) => a.key === "director");
    expect(director).toMatchObject({ model: "claude-sonnet-5-5", monthlyBudgetCents: 1500 });
    await expect(
      updateAgentSettings(ctx, "director", { enabled: false, model: "gpt-x" as never, monthlyBudgetCents: 0, instructions: "" }),
    ).rejects.toThrow();
  });
});

describe("formato", () => {
  it("extrae dominios", () => {
    expect(domainFromUrl("https://WWW.ejemplo.com.uy/a?b")).toBe("ejemplo.com.uy");
    expect(domainFromUrl("ejemplo.com")).toBe("ejemplo.com");
    expect(domainFromUrl("localhost")).toBeNull();
    expect(domainFromUrl("")).toBeNull();
  });
});
