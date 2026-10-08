import Tabs from 'expo-router/js-tabs';
import type { ColorValue } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icono, type NombreIcono } from '../../componentes/Icono';
import { colores, fuentes } from '../../tema';

const icono = (nombre: NombreIcono) =>
  function IconoPestana({ color, focused }: { color: ColorValue; focused: boolean }) {
    return <Icono nombre={nombre} color={String(color)} relleno={focused && nombre !== 'buscar'} tam={24} />;
  };

export default function Pestanas() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colores.tinta },
        headerTintColor: colores.blanco,
        headerTitleStyle: { fontFamily: fuentes.titulo, fontSize: 20 },
        tabBarActiveTintColor: colores.banda,
        tabBarInactiveTintColor: colores.gris,
        tabBarLabelStyle: { fontFamily: fuentes.semi, fontSize: 13 },
        tabBarStyle: { backgroundColor: colores.blanco, borderTopColor: colores.borde, height: 62 + insets.bottom, paddingTop: 6 },
        sceneStyle: { backgroundColor: colores.fondo },
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Buscar', headerShown: false, tabBarIcon: icono('buscar') }} />
      <Tabs.Screen name="alertas" options={{ title: 'Alertas', tabBarIcon: icono('campana') }} />
      <Tabs.Screen name="publicar" options={{ title: 'Publicar', headerTitle: 'Publicá tu vehículo', tabBarIcon: icono('mas') }} />
      <Tabs.Screen name="cuenta" options={{ title: 'Cuenta', tabBarIcon: icono('persona') }} />
    </Tabs>
  );
}
