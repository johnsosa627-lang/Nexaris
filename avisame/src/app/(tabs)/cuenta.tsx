// Cuenta: ingreso, publicaciones, panel de automotora, legales y borrar la cuenta.
import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { confirmar } from '../../componentes/confirmar';
import { Ingreso } from '../../componentes/Ingreso';
import { Aviso, Cargando, Fila, Pantalla, Separador, Tarjeta, Texto, Titulo } from '../../componentes/ui';
import { api, mensajeError } from '../../datos/api';
import { useSesion } from '../../estado/Sesion';
import { colores } from '../../tema';

export default function Cuenta() {
  const { usuario, listo } = useSesion();
  const [error, setError] = useState<string | null>(null);
  const [borrando, setBorrando] = useState(false);

  if (!listo || borrando) return <Cargando texto={borrando ? 'Borrando tu cuenta…' : undefined} />;

  const borrarCuenta = () =>
    confirmar(
      'Borrar mi cuenta',
      'Se borran para siempre tus publicaciones y fotos, tus búsquedas y alertas, y tu automotora (si tenés). Si pagás un plan, se cancela la suscripción en Mercado Pago. No se puede deshacer.',
      'Borrar todo',
      async () => {
        setBorrando(true);
        setError(null);
        try {
          await api.borrarCuenta();
          router.navigate('/');
        } catch (e) {
          setError(mensajeError(e));
        } finally {
          setBorrando(false);
        }
      },
    );

  return (
    <Pantalla>
      {!usuario ? (
        <>
          <Titulo>Ingresá</Titulo>
          <Texto style={{ color: colores.gris, marginTop: 6, marginBottom: 16 }}>Para publicar, guardar búsquedas y recibir avisos.</Texto>
          <Tarjeta>
            <Ingreso />
          </Tarjeta>
        </>
      ) : (
        <>
          <Titulo>Tu cuenta</Titulo>
          <Texto style={{ color: colores.gris, marginTop: 4 }}>{usuario.email}</Texto>
          {error ? <View style={{ marginTop: 12 }}><Aviso tipo="error">{error}</Aviso></View> : null}
          <Tarjeta style={{ marginTop: 16, paddingVertical: 4 }}>
            <Fila icono="auto" titulo="Mis publicaciones" detalle="Editar, pausar, marcar como vendido o borrar" onPress={() => router.push('/mis-publicaciones')} />
            <Fila icono="campana" titulo="Mis alertas y búsquedas" onPress={() => router.navigate('/alertas')} />
            <Fila icono="tienda" titulo="Panel de automotora" detalle="Inventario, clientes y plan" onPress={() => router.push('/automotora')} />
          </Tarjeta>
        </>
      )}

      <Tarjeta style={{ marginTop: 16, paddingVertical: 4 }}>
        <Fila icono="candado" titulo="Política de privacidad" onPress={() => router.push('/privacidad')} />
        <Fila icono="info" titulo="Términos de uso" onPress={() => router.push('/terminos')} />
      </Tarjeta>

      {usuario ? (
        <Tarjeta style={{ marginTop: 16, paddingVertical: 4 }}>
          <Fila icono="salir" titulo="Salir" onPress={() => api.salir()} />
          <Separador />
          <Fila icono="basura" titulo="Borrar mi cuenta" detalle="Borra todos tus datos y cancela tu suscripción" peligro onPress={borrarCuenta} />
        </Tarjeta>
      ) : null}
      <Texto style={{ color: colores.grisClaro, fontSize: 13, textAlign: 'center', marginTop: 24 }}>Avisame · Hecho en Uruguay</Texto>
    </Pantalla>
  );
}
