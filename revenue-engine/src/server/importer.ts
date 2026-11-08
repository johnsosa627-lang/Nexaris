/**
 * Importar empresas pegando una lista (copiada de una planilla de Google/Excel, o escrita a mano).
 * Acepta columnas separadas por tabulador, punto y coma o coma. Columnas: nombre, sitio web, ciudad, sector.
 * Si la primera fila tiene títulos (nombre, web, ciudad...), se usan para ubicar las columnas.
 */
import type { Ctx } from "./context";
import { assertInternal } from "./context";
import { createCompany } from "./crm";
import { UserError } from "./errors";
import { errorMessageOf } from "./util";

export const MAX_IMPORT_ROWS = 200;

type Row = { name: string; website: string; city: string; sector: string };

const HEADER_ALIASES: Record<keyof Row, RegExp> = {
  name: /^(nombre|empresa|raz[oó]n social|name|company)$/i,
  website: /^(sitio|sitio web|web|p[aá]gina|url|website|dominio)$/i,
  city: /^(ciudad|localidad|departamento|city)$/i,
  sector: /^(sector|rubro|categor[ií]a|industria|industry)$/i,
};

function splitLine(line: string, delimiter: string): string[] {
  if (delimiter !== ",") return line.split(delimiter).map((c) => c.trim());
  // CSV con comillas
  const out: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else quoted = !quoted;
    } else if (ch === "," && !quoted) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

export function parseCompanyList(text: string): Row[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.replace(/\s+$/, "")) // solo el final: un tabulador al inicio marca una columna vacía
    .filter((l) => l.trim());
  if (lines.length === 0) return [];
  const first = lines[0];
  const delimiter = first.includes("\t") ? "\t" : first.includes(";") ? ";" : ",";
  const firstCells = splitLine(first, delimiter);
  const order: (keyof Row)[] = ["name", "website", "city", "sector"];
  let mapping: (keyof Row | null)[] = order;
  let start = 0;
  const headerHits = firstCells.map((c) => (Object.keys(HEADER_ALIASES) as (keyof Row)[]).find((k) => HEADER_ALIASES[k].test(c)) ?? null);
  if (headerHits.some(Boolean)) {
    mapping = headerHits;
    start = 1;
  }
  const rows: Row[] = [];
  for (const line of lines.slice(start)) {
    const cells = splitLine(line, delimiter);
    const row: Row = { name: "", website: "", city: "", sector: "" };
    mapping.forEach((key, i) => {
      if (key && cells[i] !== undefined) row[key] = cells[i].replace(/^"|"$/g, "").trim();
    });
    if (row.name || row.website) rows.push(row);
  }
  return rows;
}

export type ImportResult = {
  created: number;
  skipped: { line: number; name: string; reason: string }[];
};

export async function importCompanies(
  ctx: Ctx,
  text: string,
  defaults: { city?: string; sector?: string; country?: string } = {},
): Promise<ImportResult> {
  assertInternal(ctx);
  const rows = parseCompanyList(text);
  if (rows.length === 0) throw new UserError("No se encontraron empresas en el texto pegado.");
  if (rows.length > MAX_IMPORT_ROWS) {
    throw new UserError(`Se pueden importar hasta ${MAX_IMPORT_ROWS} empresas por vez (pegaste ${rows.length}).`);
  }
  const result: ImportResult = { created: 0, skipped: [] };
  for (const [i, r] of rows.entries()) {
    try {
      await createCompany(ctx, {
        name: r.name || r.website,
        website: r.website,
        city: r.city || defaults.city,
        sector: r.sector || defaults.sector,
        country: defaults.country || "UY",
        source: "planilla",
      });
      result.created++;
    } catch (err) {
      result.skipped.push({ line: i + 1, name: r.name || r.website, reason: errorMessageOf(err) });
    }
  }
  return result;
}
