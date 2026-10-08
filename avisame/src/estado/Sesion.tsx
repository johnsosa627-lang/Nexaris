import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '../datos/api';
import type { Usuario } from '../datos/tipos';
import { activarNotificaciones } from '../servicios/notificaciones';

type Ctx = { usuario: Usuario | null; listo: boolean };
const SesionCtx = createContext<Ctx>({ usuario: null, listo: false });

export function SesionProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Ctx>({ usuario: null, listo: false });

  useEffect(() => {
    let vivo = true;
    api.usuario().then((u) => vivo && setEstado({ usuario: u, listo: true }));
    const dejar = api.escucharSesion((u) => setEstado({ usuario: u, listo: true }));
    return () => {
      vivo = false;
      dejar();
    };
  }, []);

  // Si la persona ya dio permiso de notificaciones, se actualiza el token al entrar.
  useEffect(() => {
    if (estado.usuario) activarNotificaciones({ pedirPermiso: false }).catch(() => {});
  }, [estado.usuario]);

  return <SesionCtx.Provider value={estado}>{children}</SesionCtx.Provider>;
}

export function useSesion(): Ctx {
  return useContext(SesionCtx);
}
