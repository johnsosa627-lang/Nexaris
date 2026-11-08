import { afterEach, describe, expect, it } from "vitest";
import { addUser, makeWorkspace } from "./helpers";
import { decideApproval, registerExecutor, requestAction, unregisterExecutor } from "@/server/gateway";
import { getPolicyLevel, pauseAutomations, resumeAutomations, setPolicyLevel } from "@/server/security";
import { listAudit } from "@/server/security";

afterEach(() => unregisterExecutor("enviar_correo_externo"));

describe("niveles de autonomía", () => {
  it("nivel 1 se permite al instante y queda registrado", async () => {
    const ctx = await makeWorkspace();
    const r = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: "director" },
      actionType: "analizar_datos",
      summary: "Analizar empresa",
    });
    expect(r.outcome).toBe("auto");
    const log = await listAudit(ctx);
    expect(log.some((l) => l.action === "accion.automatica")).toBe(true);
  });

  it("nivel 2 queda pendiente de aprobación", async () => {
    const ctx = await makeWorkspace();
    const r = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: "email_engine" },
      actionType: "enviar_correo_externo",
      summary: "Enviar correo",
    });
    expect(r).toMatchObject({ outcome: "pending", level: 2 });
  });

  it("un agente no puede pedir acciones que no le corresponden", async () => {
    const ctx = await makeWorkspace();
    const r = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: "seo_engine" },
      actionType: "realizar_pago",
      summary: "Pagar",
    });
    expect(r.outcome).toBe("blocked");
  });

  it("cualquier acción con costo pasa a nivel 3", async () => {
    const ctx = await makeWorkspace();
    const r = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: "director" },
      actionType: "analizar_datos",
      summary: "Análisis pago",
      estimatedCostCents: 500,
    });
    expect(r).toMatchObject({ outcome: "pending", level: 3 });
  });

  it("no se puede bajar el nivel de una acción por debajo de su mínimo", async () => {
    const ctx = await makeWorkspace();
    await expect(setPolicyLevel(ctx, "realizar_pago", 1)).rejects.toThrow(/no puede tener un nivel menor/);
    await expect(setPolicyLevel(ctx, "enviar_correo_externo", 1)).rejects.toThrow();
    // Subir sí se puede
    await setPolicyLevel(ctx, "crear_borrador", 2);
    expect(await getPolicyLevel(ctx.workspaceId, "crear_borrador")).toBe(2);
  });

  it("solo el dueño cambia niveles", async () => {
    const owner = await makeWorkspace();
    const team = await addUser(owner.workspaceId, "team");
    await expect(setPolicyLevel(team, "crear_borrador", 2)).rejects.toThrow(/dueño/);
  });
});

describe("botón de parada", () => {
  it("bloquea las acciones de los agentes mientras está activo", async () => {
    const ctx = await makeWorkspace();
    await pauseAutomations(ctx, "Prueba");
    const r = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: "director" },
      actionType: "analizar_datos",
      summary: "x",
    });
    expect(r).toMatchObject({ outcome: "blocked", reason: "Las automatizaciones están detenidas." });
    await resumeAutomations(ctx);
    const r2 = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: "director" },
      actionType: "analizar_datos",
      summary: "x",
    });
    expect(r2.outcome).toBe("auto");
  });

  it("el equipo puede detener pero solo el dueño puede reanudar", async () => {
    const owner = await makeWorkspace();
    const team = await addUser(owner.workspaceId, "team");
    await pauseAutomations(team, "Vi algo raro");
    await expect(resumeAutomations(team)).rejects.toThrow(/dueño/);
    await resumeAutomations(owner);
  });

  it("una acción aprobada no se ejecuta si las automatizaciones están detenidas", async () => {
    const ctx = await makeWorkspace();
    let ejecutadas = 0;
    registerExecutor("enviar_correo_externo", async () => {
      ejecutadas++;
      return { ok: true };
    });
    const r = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: "email_engine" },
      actionType: "enviar_correo_externo",
      summary: "correo",
    });
    if (r.outcome !== "pending") throw new Error("esperaba pendiente");
    await pauseAutomations(ctx, "pausa");
    const result = await decideApproval(ctx, { approvalId: r.approvalId, decision: "aprobar" });
    expect(result?.status).toBe("aprobada");
    expect(ejecutadas).toBe(0);
  });
});

describe("aprobaciones", () => {
  async function pending(ctx: { workspaceId: string }, level: 2 | 3) {
    const r = await requestAction({
      workspaceId: ctx.workspaceId,
      actor: { type: "agent", agentKey: level === 2 ? "email_engine" : "advertising_engine" },
      actionType: level === 2 ? "enviar_correo_externo" : "gastar_dinero",
      summary: "algo",
    });
    if (r.outcome !== "pending") throw new Error("esperaba pendiente");
    return r.approvalId;
  }

  it("sin integración conectada, aprobar NO finge que se ejecutó", async () => {
    const ctx = await makeWorkspace();
    const id = await pending(ctx, 2);
    const result = await decideApproval(ctx, { approvalId: id, decision: "aprobar" });
    expect(result?.status).toBe("aprobada");
    expect(JSON.stringify(result?.result)).toMatch(/no se realizó nada/);
  });

  it("con ejecutor conectado, se ejecuta una sola vez", async () => {
    const ctx = await makeWorkspace();
    let calls = 0;
    registerExecutor("enviar_correo_externo", async () => {
      calls++;
      return { enviado: true };
    });
    const id = await pending(ctx, 2);
    const result = await decideApproval(ctx, { approvalId: id, decision: "aprobar" });
    expect(result?.status).toBe("ejecutada");
    await expect(decideApproval(ctx, { approvalId: id, decision: "aprobar" })).rejects.toThrow(/ya fue decidida/);
    expect(calls).toBe(1);
  });

  it("si el ejecutor falla, queda como fallida con el error", async () => {
    const ctx = await makeWorkspace();
    registerExecutor("enviar_correo_externo", async () => {
      throw new Error("Gmail no respondió");
    });
    const id = await pending(ctx, 2);
    const result = await decideApproval(ctx, { approvalId: id, decision: "aprobar" });
    expect(result?.status).toBe("fallida");
    expect(JSON.stringify(result?.result)).toContain("Gmail no respondió");
  });

  it("nivel 3: solo el dueño y escribiendo AUTORIZO", async () => {
    const owner = await makeWorkspace();
    const team = await addUser(owner.workspaceId, "team");
    const id = await pending(owner, 3);
    await expect(decideApproval(team, { approvalId: id, decision: "aprobar", confirmation: "AUTORIZO" })).rejects.toThrow(
      /solo las puede autorizar el dueño/,
    );
    await expect(decideApproval(owner, { approvalId: id, decision: "aprobar" })).rejects.toThrow(/AUTORIZO/);
    const ok = await decideApproval(owner, { approvalId: id, decision: "aprobar", confirmation: "autorizo" });
    expect(ok?.status).toBe("aprobada");
  });

  it("el equipo puede rechazar", async () => {
    const owner = await makeWorkspace();
    const team = await addUser(owner.workspaceId, "team");
    const id = await pending(owner, 3);
    const r = await decideApproval(team, { approvalId: id, decision: "rechazar", note: "No" });
    expect(r?.status).toBe("rechazada");
  });

  it("no se pueden decidir solicitudes de otro espacio de trabajo", async () => {
    const a = await makeWorkspace("A");
    const b = await makeWorkspace("B");
    const id = await pending(a, 2);
    await expect(decideApproval(b, { approvalId: id, decision: "aprobar" })).rejects.toThrow(/No se encontró/);
  });

  it("los usuarios del portal (clientes) no pueden aprobar", async () => {
    const owner = await makeWorkspace();
    const client = await addUser(owner.workspaceId, "client");
    const id = await pending(owner, 2);
    await expect(decideApproval(client, { approvalId: id, decision: "aprobar" })).rejects.toThrow(/permiso/);
  });
});
