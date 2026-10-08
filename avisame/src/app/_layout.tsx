// Solo los pesos que se usan (importar el paquete entero suma todas las variantes).
import { Barlow_400Regular } from '@expo-google-fonts/barlow/400Regular';
import { Barlow_500Medium } from '@expo-google-fonts/barlow/500Medium';
import { Barlow_600SemiBold } from '@expo-google-fonts/barlow/600SemiBold';
import { Barlow_700Bold } from '@expo-google-fonts/barlow/700Bold';
import { BarlowSemiCondensed_600SemiBold } from '@expo-google-fonts/barlow-semi-condensed/600SemiBold';
import { BarlowSemiCondensed_700Bold } from '@expo-google-fonts/barlow-semi-condensed/700Bold';
import { useFonts } from 'expo-font';
import { router, Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import { api } from '../datos/api';
import { escucharAvisosDemo, type AvisoDemo } from '../datos/apiDemo';
import { SesionProvider } from '../estado/Sesion';
import { ZonaProvider } from '../estado/Zona';
import { escucharToques } from '../servicios/notificaciones';
import { colores, fuentes } from '../tema';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function Raiz() {
  const [fuentesListas, errorFuentes] = useFonts({
    Barlow_400Regular,
    Barlow_500Medium,
    Barlow_600SemiBold,
    Barlow_700Bold,
    BarlowSemiCondensed_600SemiBold,
    BarlowSemiCondensed_700Bold,
  });

  useEffect(() => {
    if (fuentesListas || errorFuentes) SplashScreen.hideAsync().catch(() => {});
  }, [fuentesListas, errorFuentes]);

  useEffect(() => escucharToques(), []);

  if (!fuentesListas && !errorFuentes) return null;

  return (
    <SafeAreaProvider>
      <SesionProvider>
        <ZonaProvider>
          <StatusBar style="light" />
          {api.vistaPrevia ? <BandaVistaPrevia /> : null}
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colores.tinta },
              headerTintColor: colores.blanco,
              headerTitleStyle: { fontFamily: fuentes.titulo, fontSize: 20 },
              headerBackButtonDisplayMode: 'minimal',
              contentStyle: { backgroundColor: colores.fondo },
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false, title: 'Avisame' }} />
            <Stack.Screen name="vehiculo/[id]" options={{ title: 'Vehículo' }} />
            <Stack.Screen name="editar/[id]" options={{ title: 'Editar publicación' }} />
            <Stack.Screen name="ingresar" options={{ title: 'Ingresar', presentation: 'modal' }} />
            <Stack.Screen name="mis-publicaciones" options={{ title: 'Mis publicaciones' }} />
            <Stack.Screen name="automotora" options={{ title: 'Panel de automotora' }} />
            <Stack.Screen name="privacidad" options={{ title: 'Política de privacidad' }} />
            <Stack.Screen name="terminos" options={{ title: 'Términos de uso' }} />
          </Stack>
          {api.vistaPrevia ? <AvisosVistaPrevia /> : null}
        </ZonaProvider>
      </SesionProvider>
    </SafeAreaProvider>
  );
}

/** Banda fija que deja claro que son datos de ejemplo. */
function BandaVistaPrevia() {
  const insets = useSafeAreaInsets();
  return (
    <View style={[estilos.banda, { paddingTop: insets.top + 4 }]} accessibilityRole="text">
      <Text style={estilos.bandaTexto}>VISTA PREVIA · vehículos y datos de ejemplo, no reales</Text>
    </View>
  );
}

/** En la vista previa, los "avisos al celular" aparecen como un cartel arriba. */
function AvisosVistaPrevia() {
  const insets = useSafeAreaInsets();
  const [aviso, setAviso] = useState<AvisoDemo | null>(null);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const dejar = escucharAvisosDemo((a) => {
      setAviso(a);
      clearTimeout(t);
      t = setTimeout(() => setAviso(null), 9000);
    });
    return () => {
      dejar();
      clearTimeout(t);
    };
  }, []);
  if (!aviso) return null;
  return (
    <Pressable
      accessibilityRole="alert"
      onPress={() => {
        setAviso(null);
        if (aviso.vehiculoId) router.push(`/vehiculo/${aviso.vehiculoId}`);
      }}
      style={[estilos.aviso, { top: insets.top + 34 }]}
    >
      <Text style={estilos.avisoApp}>AVISAME · ahora (notificación de ejemplo)</Text>
      <Text style={estilos.avisoTitulo}>{aviso.titulo}</Text>
      <Text style={estilos.avisoCuerpo}>{aviso.cuerpo}</Text>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  banda: { backgroundColor: colores.vistaPrevia, paddingBottom: 4, alignItems: 'center' },
  bandaTexto: { color: colores.blanco, fontFamily: fuentes.semi, fontSize: 12, letterSpacing: 0.6 },
  aviso: {
    position: 'absolute', left: 12, right: 12, maxWidth: 520, alignSelf: 'center', backgroundColor: colores.blanco, borderRadius: 16,
    padding: 14, shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 10,
    borderLeftWidth: 5, borderLeftColor: colores.banda,
  },
  avisoApp: { fontFamily: fuentes.semi, fontSize: 12, color: colores.gris, letterSpacing: 0.4 },
  avisoTitulo: { fontFamily: fuentes.negrita, fontSize: 17, color: colores.tinta, marginTop: 2 },
  avisoCuerpo: { fontFamily: fuentes.normal, fontSize: 15, color: colores.tinta, marginTop: 2 },
});
