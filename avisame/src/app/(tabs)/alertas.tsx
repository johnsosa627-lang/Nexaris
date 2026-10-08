// Alertas: lo que apareció para las búsquedas guardadas, y las búsquedas en sí.
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { confirmar } from '../../componentes/confirmar';
import { Icono } from '../../componentes/Icono';
import { TarjetaVehiculo } from '../../componentes/TarjetaVehiculo';
import { Aviso, Boton, Cargando, Tarjeta, Texto, Titulo, Vacio } from '../../componentes/ui';
import { api, mensajeError } from '../../datos/api';
import type { Alerta, Busqueda } from '../../datos/tipos';
import { useSesion } from '../../estado/Sesion';
import { nombreLugar, resumenCriterios } from '../../nucleo';
import { ANCHO_MAX, colores, fuentes } from '../../tema';

export default function Alertas() {
  const { usuario, listo } = useSesion();
  const [alertas, setAlertas] = useState<Alerta[] | null>(null);
  const [busquedas, setBusquedas] = useState<Busqueda[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [recargando, setRecargando] = useState(false);

  const cargar = useCallback(async () => {
    if (!usuario) return;
    setError(null);
    try {
      const [a, b] = await Promise.all([api.alertas(), api.misBusquedas()]);
      setAlertas(a);
      setBusquedas(b);
      // Se marcan como vistas después de mostrarlas una vez.
      if (a.some((x) => !x.vista)) api.marcarAlertasVistas().catch(() => {});
    } catch (e) {
      setError(mensajeError(e));
    }
  }, [usuario]);

  useFocusEffect(
    useCallback(() => {
      cargar();
    }, [cargar]),
  );

  const borrar = (b: Busqueda) => {
    confirmar('Borrar búsqueda', '¿Dejar de avisarte por esta búsqueda?', 'Borrar', async () => {
      await api.borrarBusqueda(b.id);
      cargar();
    });
  };

  if (!listo) return <Cargando />;
  if (!usuario) {
    return (
      <Vacio icono="campana" titulo="Tus alertas" texto="Guardá una búsqueda con “Avisame cuando aparezca” y acá vas a ver todo lo que aparezca.">
        <Boton titulo="Buscar un vehículo" icono="buscar" onPress={() => router.navigate('/')} style={{ alignSelf: 'stretch', maxWidth: 360 }} />
        <Boton titulo="Ingresar" variante="secundario" onPress={() => router.push('/ingresar')} style={{ alignSelf: 'stretch', maxWidth: 360, marginTop: 10 }} />
      </Vacio>
    );
  }
  if (!alertas && !error) return <Cargando />;

  const tituloDe = (id: string) => busquedas.find((b) => b.id === id);

  return (
    <ScrollView
      style={{ backgroundColor: colores.fondo }}
      contentContainerStyle={estilos.contenido}
      refreshControl={<RefreshControl refreshing={recargando} onRefresh={async () => { setRecargando(true); await cargar(); setRecargando(false); }} />}
    >
      {error ? <Aviso tipo="error">{error}</Aviso> : null}

      <Titulo nivel={2}>Lo que apareció</Titulo>
      {alertas && alertas.length > 0 ? (
        <View style={{ marginTop: 10 }}>
          {alertas.map((a) => {
            const b = tituloDe(a.busqueda_id);
            return (
              <View key={a.id}>
                <Text style={estilos.para}>
                  {!a.vista ? <Text style={estilos.nuevo}> NUEVO </Text> : null}
                  {!a.vista ? ' ' : ''}Para tu búsqueda: {b ? resumenCriterios(b.criterios) : '—'}
                </Text>
                {a.vehiculo ? (
                  <TarjetaVehiculo v={a.vehiculo} distanciaKm={a.distancia_km} desde={b ? b.ciudad : null} />
                ) : (
                  <Tarjeta style={{ marginBottom: 14 }}>
                    <Texto style={{ color: colores.gris }}>Este vehículo ya no está disponible (se vendió o se pausó).</Texto>
                  </Tarjeta>
                )}
              </View>
            );
          })}
        </View>
      ) : (
        <Tarjeta style={{ marginTop: 10 }}>
          <Texto style={{ color: colores.gris }}>
            Todavía no apareció nada nuevo. Cuando alguien publique algo que coincida con tus búsquedas, te avisamos y lo ves acá.
          </Texto>
        </Tarjeta>
      )}

      <Titulo nivel={2} style={{ marginTop: 26 }}>Tus búsquedas guardadas</Titulo>
      {busquedas.length === 0 ? (
        <Tarjeta style={{ marginTop: 10 }}>
          <Texto style={{ color: colores.gris }}>No tenés búsquedas guardadas.</Texto>
          <Boton titulo="Buscar un vehículo" icono="buscar" chico variante="claro" onPress={() => router.navigate('/')} style={{ marginTop: 12, alignSelf: 'flex-start' }} />
        </Tarjeta>
      ) : (
        busquedas.map((b) => (
          <Tarjeta key={b.id} style={estilos.busqueda}>
            <View style={{ flex: 1 }}>
              <Text style={estilos.busquedaTitulo}>{resumenCriterios(b.criterios)}</Text>
              <Text style={estilos.busquedaDetalle}>
                📍 Desde {nombreLugar(b.departamento, b.ciudad)} · {b.autoriza_contacto ? 'Automotoras pueden contactarte' : 'Sin contacto de automotoras'}
              </Text>
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel="Borrar búsqueda" onPress={() => borrar(b)} hitSlop={10} style={{ padding: 6 }}>
              <Icono nombre="basura" color={colores.rojo} />
            </Pressable>
          </Tarjeta>
        ))
      )}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  contenido: { padding: 16, paddingBottom: 40, width: '100%', maxWidth: ANCHO_MAX, alignSelf: 'center' },
  para: { fontFamily: fuentes.media, fontSize: 14, color: colores.gris, marginBottom: 6 },
  nuevo: { backgroundColor: colores.banda, color: colores.blanco, fontFamily: fuentes.negrita, fontSize: 12 },
  busqueda: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 10 },
  busquedaTitulo: { fontFamily: fuentes.semi, fontSize: 17, color: colores.tinta },
  busquedaDetalle: { fontFamily: fuentes.normal, fontSize: 14, color: colores.gris, marginTop: 2 },
});
