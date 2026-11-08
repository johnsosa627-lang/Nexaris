import "server-only";
import { unstable_rethrow } from "next/navigation";
import { ZodError } from "zod";
import { UserError } from "@/server/errors";

export type ActionState = { ok: boolean; message: string } | null;

/** Convierte cualquier error en un mensaje entendible para la persona. */
export function errorMessage(err: unknown): string {
  if (err instanceof UserError) return err.message;
  if (err instanceof ZodError) return err.issues[0]?.message ?? "Revisá los datos ingresados.";
  console.error(err);
  return "Ocurrió un error inesperado. Probá de nuevo; si sigue pasando, revisá el registro del servidor.";
}

/** Ejecuta una acción de formulario y devuelve un estado { ok, message } para mostrar en pantalla. */
export async function run(fn: () => Promise<string | void>, okMessage = "Guardado."): Promise<ActionState> {
  try {
    const msg = await fn();
    return { ok: true, message: msg || okMessage };
  } catch (err) {
    unstable_rethrow(err);
    return { ok: false, message: errorMessage(err) };
  }
}

export function str(form: FormData, key: string): string {
  const v = form.get(key);
  return typeof v === "string" ? v : "";
}

/** Convierte "12,50" o "12.50" (dólares) en centavos. */
export function centsFromForm(form: FormData, key: string): number {
  const raw = str(form, key).trim().replace(",", ".");
  if (!raw) return 0;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) throw new UserError("Escribí un monto válido (ej. 25 o 25,50).");
  return Math.round(n * 100);
}

/** Interpreta un campo datetime-local como hora de Montevideo (UTC-3, sin horario de verano). */
export function dateFromLocalInput(value: string): Date {
  if (!value) throw new UserError("Elegí una fecha.");
  const withSeconds = value.length === 16 ? `${value}:00` : value;
  const d = new Date(`${withSeconds}-03:00`);
  if (Number.isNaN(d.getTime())) throw new UserError("La fecha no es válida.");
  return d;
}
