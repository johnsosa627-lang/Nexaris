import { ActionForm, Submit } from "@/components/action-form";
import { CompanyFields } from "@/components/company-fields";
import { Card, PageHeader } from "@/components/ui";
import { requireCtx } from "@/lib/session";
import { createCompanyAction } from "../actions";

export const metadata = { title: "Nueva empresa" };

export default async function NewCompanyPage() {
  await requireCtx();
  return (
    <>
      <PageHeader
        title="Nueva empresa"
        subtitle="Cargá solo datos que puedas comprobar. Si el sitio web ya está en el CRM, el sistema te avisa."
      />
      <Card>
        <ActionForm action={createCompanyAction} className="space-y-4">
          <CompanyFields />
          <Submit>Guardar empresa</Submit>
        </ActionForm>
      </Card>
    </>
  );
}
