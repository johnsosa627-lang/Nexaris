import Link from "next/link";
import { ActionForm, Submit } from "@/components/action-form";
import { Card, PageHeader } from "@/components/ui";
import { requireCtx } from "@/lib/session";
import { MAX_IMPORT_ROWS } from "@/server/importer";
import { importAction } from "../actions";

export const metadata = { title: "Importar empresas" };

const EXAMPLE = `Nombre\tSitio web\tCiudad\tSector
Inmobiliaria Ejemplo\tinmoejemplo.com.uy\tMontevideo\tInmobiliarias
Automotora Ejemplo\tautoejemplo.uy\tMontevideo\tAutomotoras`;

export default async function ImportPage() {
  await requireCtx();
  return (
    <>
      <div className="mb-2 text-sm">
        <Link href="/empresas" className="text-indigo-700 hover:underline">
          ← Empresas
        </Link>
      </div>
      <PageHeader
        title="Importar empresas"
        subtitle={`Pegá una lista (hasta ${MAX_IMPORT_ROWS}). Las que ya estén cargadas se saltean y te avisamos por qué.`}
      />
      <Card>
        <ActionForm action={importAction} resetOnSuccess className="space-y-4">
          <div>
            <label className="label" htmlFor="list">Lista de empresas</label>
            <textarea className="field font-mono text-xs" id="list" name="list" rows={10} required placeholder={EXAMPLE} />
            <p className="mt-1 text-xs text-slate-500">
              Una empresa por línea: <strong>nombre, sitio web, ciudad, sector</strong>. Podés copiar columnas de una planilla de
              Google o Excel, o separar con punto y coma. Si la primera línea tiene títulos, se usan para ubicar las columnas.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="sector">Sector (si la lista no lo trae)</label>
              <input className="field" id="sector" name="sector" list="sectores-import" />
              <datalist id="sectores-import">
                {["Automotoras", "Inmobiliarias", "Tiendas online", "Comercios", "Fabricantes", "Distribuidores", "Empresas de servicios"].map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="label" htmlFor="city">Ciudad (si la lista no la trae)</label>
              <input className="field" id="city" name="city" />
            </div>
            <div>
              <label className="label" htmlFor="country">País</label>
              <input className="field uppercase" id="country" name="country" maxLength={2} defaultValue="UY" />
            </div>
          </div>
          <p className="text-xs text-slate-500">
            Cargá solo empresas reales y datos públicos. Los contactos (emails, teléfonos) se agregan después, indicando de dónde salen.
          </p>
          <Submit>Importar</Submit>
        </ActionForm>
      </Card>
    </>
  );
}
