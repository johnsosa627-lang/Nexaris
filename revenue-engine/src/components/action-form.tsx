"use client";

import { createContext, useActionState, useContext, useRef, useTransition, type ReactNode } from "react";

type State = { ok: boolean; message: string } | null;

const PendingContext = createContext(false);

/**
 * Formulario que llama a una acción del servidor y muestra el resultado ("Guardado." o el error).
 *
 * El envío se hace a mano (no con `action={...}`) para que, si hay un error, los campos
 * NO se borren: React vacía automáticamente los formularios enviados con `action`.
 * Con `resetOnSuccess` se limpian los campos solo cuando se guardó bien.
 */
export function ActionForm({
  action,
  children,
  className = "",
  resetOnSuccess = false,
  confirm,
}: {
  action: (prev: State, form: FormData) => Promise<State>;
  children: ReactNode;
  className?: string;
  resetOnSuccess?: boolean;
  /** Si se indica, pide confirmación antes de enviar. */
  confirm?: string;
}) {
  const ref = useRef<HTMLFormElement>(null);
  const [state, dispatch] = useActionState(async (prev: State, form: FormData) => {
    const result = await action(prev, form);
    if (result?.ok && resetOnSuccess) ref.current?.reset();
    return result;
  }, null);
  const [pending, startTransition] = useTransition();

  return (
    <form
      ref={ref}
      className={className}
      onSubmit={(e) => {
        e.preventDefault();
        if (pending) return;
        if (confirm && !window.confirm(confirm)) return;
        const submitter = (e.nativeEvent as SubmitEvent).submitter as HTMLElement | null;
        const data = new FormData(e.currentTarget, submitter);
        startTransition(() => dispatch(data));
      }}
    >
      <PendingContext value={pending}>{children}</PendingContext>
      {state ? (
        <p role="status" className={`mt-2 text-sm ${state.ok ? "text-emerald-700" : "text-red-700"}`}>
          {state.message}
        </p>
      ) : null}
    </form>
  );
}

export function Submit({
  children,
  variant = "primary",
  size,
  name,
  value,
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger";
  size?: "sm";
  name?: string;
  value?: string;
}) {
  const pending = useContext(PendingContext);
  return (
    <button
      type="submit"
      name={name}
      value={value}
      disabled={pending}
      className={`btn btn-${variant} ${size === "sm" ? "btn-sm" : ""}`}
    >
      {pending ? "Procesando…" : children}
    </button>
  );
}
