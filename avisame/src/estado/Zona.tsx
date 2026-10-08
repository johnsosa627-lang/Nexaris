// La zona de la persona (departamento y ciudad, o la ubicación del celular).
// Se recuerda entre sesiones. Nunca filtra resultados: solo ordena y mide distancias.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { UBICACION_POR_DEFECTO, ubicacionDe, type Ubicacion } from '../nucleo';
import { ubicacionDelCelular } from '../servicios/ubicacion';

export type Zona = Ubicacion & { origen: 'elegida' | 'celular' | 'predeterminada' };

type Ctx = {
  zona: Zona;
  elegir: (departamento: string, ciudad: string) => void;
  usarCelular: () => Promise<void>;
};

const CLAVE = 'avisame:zona';
const ZonaCtx = createContext<Ctx | null>(null);

export function ZonaProvider({ children }: { children: ReactNode }) {
  const [zona, setZona] = useState<Zona>({ ...UBICACION_POR_DEFECTO, origen: 'predeterminada' });

  useEffect(() => {
    AsyncStorage.getItem(CLAVE)
      .then((g) => {
        if (g) setZona(JSON.parse(g));
      })
      .catch(() => {});
  }, []);

  const guardar = useCallback((z: Zona) => {
    setZona(z);
    AsyncStorage.setItem(CLAVE, JSON.stringify(z)).catch(() => {});
  }, []);

  const elegir = useCallback(
    (departamento: string, ciudad: string) => {
      const u = ubicacionDe(departamento, ciudad);
      if (u) guardar({ ...u, origen: 'elegida' });
    },
    [guardar],
  );

  const usarCelular = useCallback(async () => {
    const u = await ubicacionDelCelular();
    guardar({ ...u, origen: 'celular' });
  }, [guardar]);

  const valor = useMemo(() => ({ zona, elegir, usarCelular }), [zona, elegir, usarCelular]);
  return <ZonaCtx.Provider value={valor}>{children}</ZonaCtx.Provider>;
}

export function useZona(): Ctx {
  const c = useContext(ZonaCtx);
  if (!c) throw new Error('useZona fuera de ZonaProvider');
  return c;
}
