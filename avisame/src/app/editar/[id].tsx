import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { FormularioVehiculo } from '../../componentes/FormularioVehiculo';
import { Cargando, Pantalla, Vacio } from '../../componentes/ui';
import { api } from '../../datos/api';
import type { Vehiculo } from '../../datos/tipos';
import { useSesion } from '../../estado/Sesion';

export default function Editar() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { usuario } = useSesion();
  const [v, setV] = useState<Vehiculo | null | undefined>(undefined);

  useEffect(() => {
    api.vehiculo(String(id)).then(setV).catch(() => setV(null));
  }, [id]);

  if (v === undefined) return <Cargando />;
  if (!v || !usuario || v.owner_id !== usuario.id) return <Vacio icono="candado" titulo="No podés editar esta publicación" />;
  return (
    <Pantalla>
      <FormularioVehiculo inicial={v} onGuardado={(nuevo) => router.replace(`/vehiculo/${nuevo}`)} />
    </Pantalla>
  );
}
