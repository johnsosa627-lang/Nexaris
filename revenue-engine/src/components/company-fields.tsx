type Values = {
  name?: string | null;
  website?: string | null;
  country?: string | null;
  city?: string | null;
  sector?: string | null;
  notes?: string | null;
};

const SECTORS = [
  "Automotoras",
  "Inmobiliarias",
  "Tiendas online",
  "Comercios",
  "Fabricantes",
  "Distribuidores",
  "Empresas de servicios",
];

/** Campos de empresa, usados en "Nueva empresa" y en "Editar". */
export function CompanyFields({ values = {} }: { values?: Values }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <label className="label" htmlFor="name">Nombre de la empresa *</label>
        <input className="field" id="name" name="name" defaultValue={values.name ?? ""} required minLength={2} />
      </div>
      <div className="sm:col-span-2">
        <label className="label" htmlFor="website">Sitio web</label>
        <input
          className="field"
          id="website"
          name="website"
          placeholder="empresa.com.uy"
          defaultValue={values.website ?? ""}
          inputMode="url"
        />
      </div>
      <div>
        <label className="label" htmlFor="sector">Sector</label>
        <input className="field" id="sector" name="sector" list="sectores" defaultValue={values.sector ?? ""} />
        <datalist id="sectores">
          {SECTORS.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </div>
      <div>
        <label className="label" htmlFor="city">Ciudad</label>
        <input className="field" id="city" name="city" defaultValue={values.city ?? ""} />
      </div>
      <div>
        <label className="label" htmlFor="country">País (código de 2 letras)</label>
        <input
          className="field uppercase"
          id="country"
          name="country"
          maxLength={2}
          defaultValue={values.country ?? "UY"}
        />
      </div>
      <div className="sm:col-span-2">
        <label className="label" htmlFor="notes">Notas internas</label>
        <textarea className="field" id="notes" name="notes" rows={3} defaultValue={values.notes ?? ""} />
      </div>
    </div>
  );
}
