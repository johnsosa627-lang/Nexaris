import { router } from 'expo-router';
import { Ingreso } from '../componentes/Ingreso';
import { Pantalla, Tarjeta, Titulo } from '../componentes/ui';

export default function Ingresar() {
  return (
    <Pantalla>
      <Titulo style={{ marginBottom: 14 }}>Ingresá con tu email</Titulo>
      <Tarjeta>
        <Ingreso onListo={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
      </Tarjeta>
    </Pantalla>
  );
}
