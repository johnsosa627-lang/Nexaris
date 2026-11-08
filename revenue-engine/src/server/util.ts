import { ZodError } from "zod";
import { UserError } from "./errors";

/** Mensaje entendible de un error (para listas de resultados, no para mostrar detalles internos). */
export function errorMessageOf(err: unknown): string {
  if (err instanceof UserError) return err.message;
  if (err instanceof ZodError) return err.issues[0]?.message ?? "Datos inválidos.";
  return "Error inesperado.";
}
