// Publicar: formulario para particulares (las automotoras cargan desde su panel).
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { FormularioVehiculo } from '../../componentes/FormularioVehiculo';
import { Ingreso } from '../../componentes/Ingreso';
import { Aviso, Boton, Cargando, Fila, Pantalla, Tarjeta, Texto, Titulo } from '../../componentes/ui';
import { api } from '../../datos/api';
import type { Automotora } from '../../datos/tipos';
import { useSesion } from '../../estado/Sesion';
import { colores } from '../../tema';

export default function Publicar() {
  const { usuario, listo } = useSesion();
  const [publicado, setPublicado] = useState<string | null>(null);
  const [automotora, setAutomotora] = useState<Automotora | null>(null);
  const [vuelta, setVuelta] = useState(0);

  useFocusEffect(
    useCallback(() => {
      if (usuario) api.miAutomotora().then(setAutomotora).catch(() => {});
    }, [usuario]),
  );

  if (!listo) return <Cargando />;

  if (!usuario) {
    return (
      <Pantalla>
        <Titulo>Publicá tu vehículo</Titulo>
        <Texto style={{ color: colores.gris, marginTop: 6, marginBottom: 16 }}>
          Gratis, para particulares y automotoras. Le avisamos al instante a quienes estén buscando uno como el tuyo.
        </Texto>
        <Tarjeta>
          <Ingreso explicacion="Para publicar, ingresá con tu email. Sin contraseña: te mandamos un código." />
        </Tarjeta>
      </Pantalla>
    );
  }

  if (publicado) {
    return (
      <Pantalla>
        <Aviso tipo="ok">¡Listo! Tu vehículo ya está publicado.</Aviso>
        <Texto style={{ marginBottom: 16 }}>Si alguien lo estaba buscando, ya le llegó el aviso. Podés editarlo, pausarlo o marcarlo como vendido cuando quieras.</Texto>
        <Boton titulo="Ver mi publicación" icono="auto" onPress={() => router.push(`/vehiculo/${publicado}`)} />
        <Boton titulo="Publicar otro" variante="secundario" onPress={() => { setPublicado(null); setVuelta((n) => n + 1); }} style={{ marginTop: 10 }} />
      </Pantalla>
    );
  }

  return (
    <Pantalla>
      {automotora ? (
        <Tarjeta style={{ marginBottom: 8 }}>
          <Fila icono="tienda" titulo={`Cargar en ${automotora.nombre}`} detalle="Desde el panel, con los datos de tu automotora" onPress={() => router.push('/automotora?pestana=cargar')} />
        </Tarjeta>
      ) : (
        <Tarjeta style={{ marginBottom: 8 }}>
          <Fila icono="tienda" titulo="¿Sos automotora?" detalle="Cargá tu inventario y encontrá clientes" onPress={() => router.push('/automotora')} />
        </Tarjeta>
      )}
      <FormularioVehiculo key={vuelta} onGuardado={setPublicado} />
    </Pantalla>
  );
}
