import { es, type Dictionary } from "./es";

const dictionaries: Record<string, Dictionary> = { es };

/** Devuelve los textos del idioma pedido (por ahora solo español). */
export function getDictionary(locale: string = "es"): Dictionary {
  return dictionaries[locale] ?? es;
}

export const t = getDictionary("es");
