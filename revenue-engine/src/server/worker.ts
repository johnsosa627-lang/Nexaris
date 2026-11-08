/**
 * Trabajador en segundo plano: cada pocos segundos procesa la cola de diagnósticos.
 * Corre dentro del mismo servidor (no hace falta otro servicio). Se inicia desde src/instrumentation.ts.
 */
import { processQueue, recoverStale } from "./diagnosis";

const INTERVAL_MS = 5_000;
const g = globalThis as unknown as { __reWorker?: { timer: NodeJS.Timeout; running: boolean; ticks: number } };

async function tick() {
  const state = g.__reWorker;
  if (!state || state.running) return;
  state.running = true;
  try {
    if (state.ticks % 60 === 0) await recoverStale(); // cada ~5 minutos
    state.ticks++;
    await processQueue();
  } catch (err) {
    console.error("[trabajador] error procesando la cola:", err);
  } finally {
    state.running = false;
  }
}

export function startWorker() {
  if (g.__reWorker) return;
  g.__reWorker = { timer: setInterval(tick, INTERVAL_MS), running: false, ticks: 0 };
  console.log("[trabajador] cola de diagnósticos activa");
}

/** Despierta al trabajador ya (en vez de esperar al próximo ciclo). */
export function kickWorker() {
  startWorker();
  void tick();
}
