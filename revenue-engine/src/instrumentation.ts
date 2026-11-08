/** Se ejecuta una vez al arrancar el servidor: inicia la cola de diagnósticos. */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs" && process.env.DISABLE_WORKER !== "true") {
    const { startWorker } = await import("./server/worker");
    startWorker();
  }
}
