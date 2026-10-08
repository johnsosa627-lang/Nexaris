import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { TarjetaVehiculo } from '../componentes/TarjetaVehiculo';
import { Aviso, Boton, Cargando, Pantalla, Vacio } from '../componentes/ui';
import { api, mensajeError } from '../datos/api';
import type { Vehiculo } from '../datos/tipos';
import { useSesion } from '../estado/Sesion';

export default function MisPublicaciones() {
  const { usuario } = useSesion();
  const [lista, setLista] = useState<Vehiculo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!usuario) return;
      api.misVehiculos().then(setLista).catch((e) => setError(mensajeError(e)));
    }, [usuario]),
  );

  if (!usuario) {
    return (
      <Vacio icono="persona" titulo="Ingresá para ver tus publicaciones">
        <Boton titulo="Ingresar" onPress={() => router.push('/ingresar')} />
      </Vacio>
    );
  }
  if (error) return <Pantalla><Aviso tipo="error">{error}</Aviso></Pantalla>;
  if (!lista) return <Cargando />;
  if (lista.length === 0) {
    return (
      <Vacio icono="auto" titulo="Todavía no publicaste" texto="Publicar es gratis y le avisamos al instante a quienes buscan uno como el tuyo.">
        <Boton titulo="📢 Publicá tu vehículo" onPress={() => router.navigate('/publicar')} />
      </Vacio>
    );
  }
  return (
    <Pantalla>
      {lista.map((v) => (
        <TarjetaVehiculo key={v.id} v={v} estado />
      ))}
    </Pantalla>
  );
}
