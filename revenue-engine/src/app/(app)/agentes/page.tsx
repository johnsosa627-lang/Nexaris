import { ActionForm, Submit } from "@/components/action-form";
import { Badge, Card, PageHeader, levelTone } from "@/components/ui";
import { t } from "@/i18n";
import { AI_MODELS, type ActionType } from "@/lib/catalog";
import { requireCtx } from "@/lib/session";
import { listAgents } from "@/server/agents";
import { getPolicyLevels } from "@/server/security";
import { updateAgentAction } from "./actions";

export const metadata = { title: "Agentes" };

const MODEL_LABELS: Record<string, string> = {
  "claude-opus-5-5": "Claude Opus 5.5 · mejor calidad (US$4 / US$20 por millón de tokens)",
  "claude-sonnet-5-5": "Claude Sonnet 5.5 · equilibrado (US$2 / US$10)",
  "claude-haiku-5-5": "Claude Haiku 5.5 · económico (US$0,10 / US$0,50)",
};

export default async function AgentsPage() {
  const ctx = await requireCtx();
  const [agents, levels] = await Promise.all([listAgents(ctx), getPolicyLevels(ctx.workspaceId)]);
  const isOwner = ctx.role === "owner";

  return (
    <>
      <PageHeader
        title="Agentes"
        subtitle="El equipo de especialistas. Un agente solo se puede encender cuando su lógica está construida y probada; mientras tanto podés dejar preparado su modelo, presupuesto e instrucciones."
      />
      <div className="grid gap-4 md:grid-cols-2">
        {agents.map((a) => {
          const info = t.agents[a.key as keyof typeof t.agents];
          return (
            <Card
              key={a.key}
              title={info.name}
              actions={
                a.runnable ? (
                  <Badge tone={a.enabled ? "green" : "slate"}>{a.enabled ? "Encendido" : "Apagado"}</Badge>
                ) : (
                  <Badge tone="slate">En preparación · Fase {a.phase}</Badge>
                )
              }
            >
              <p className="text-sm text-slate-700">{info.description}</p>
              <div className="mt-3">
                <div className="label">Acciones que puede pedir</div>
                <div className="flex flex-wrap gap-1">
                  {a.actions.map((act: ActionType) => (
                    <Badge key={act} tone={levelTone(levels[act])}>
                      {t.actionTypes[act]} · N{levels[act]}
                    </Badge>
                  ))}
                </div>
              </div>
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-semibold text-indigo-700">Configurar</summary>
                <ActionForm action={updateAgentAction} className="mt-3 space-y-3">
                  <input type="hidden" name="agentKey" value={a.key} />
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="enabled" defaultChecked={a.enabled} disabled={!a.runnable || !isOwner} />
                    Encendido {a.runnable ? "" : "(disponible cuando el agente esté construido)"}
                  </label>
                  <div>
                    <label className="label" htmlFor={`model-${a.key}`}>Modelo de IA</label>
                    <select className="field" id={`model-${a.key}`} name="model" defaultValue={a.model} disabled={!isOwner}>
                      {AI_MODELS.map((m) => (
                        <option key={m} value={m}>
                          {MODEL_LABELS[m] ?? m}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label" htmlFor={`budget-${a.key}`}>Presupuesto mensual de IA (US$)</label>
                    <input
                      className="field"
                      id={`budget-${a.key}`}
                      name="budget"
                      inputMode="decimal"
                      defaultValue={(a.monthlyBudgetCents / 100).toString()}
                      disabled={!isOwner}
                    />
                  </div>
                  <div>
                    <label className="label" htmlFor={`instr-${a.key}`}>Instrucciones adicionales</label>
                    <textarea
                      className="field"
                      id={`instr-${a.key}`}
                      name="instructions"
                      rows={2}
                      defaultValue={a.instructions}
                      disabled={!isOwner}
                      placeholder="Ej: priorizar automotoras de Montevideo"
                    />
                  </div>
                  {isOwner ? <Submit>Guardar</Submit> : <p className="text-xs text-slate-500">Solo el dueño puede cambiar esto.</p>}
                </ActionForm>
              </details>
            </Card>
          );
        })}
      </div>
    </>
  );
}
