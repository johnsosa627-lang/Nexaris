// Buscar: la pantalla principal. Escribo → la app entiende → me muestra vehículos.
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, SectionList, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BarraMatricula } from '../../componentes/BarraMatricula';
import { FondoRuta } from '../../componentes/FondoRuta';
import { GuardarBusqueda } from '../../componentes/GuardarBusqueda';
import { Icono } from '../../componentes/Icono';
import { SelectorZona } from '../../componentes/SelectorZona';
import { TarjetaVehiculo } from '../../componentes/TarjetaVehiculo';
import { Aviso, Boton, Cargando } from '../../componentes/ui';
import { api, mensajeError } from '../../datos/api';
import type { Vehiculo } from '../../datos/tipos';
import { useZona } from '../../estado/Zona';
import {
  buscar,
  etiquetas,
  interpretar,
  quitarCriterio,
  textoDesdeCriterios,
  type ClaveCriterio,
  type Criterios,
  type Resultado,
} from '../../nucleo';
import { ANCHO_MAX, colores, fuentes } from '../../tema';

const EJEMPLOS = [
  'Hyundai Creta 2022 o más nueva, hasta 18.000 dólares',
  'Pickup 4x4 diésel en Salto',
  'Corolla automático hasta 20 mil dólares',
  'Hatch manual hasta USD 10.000',
];

export default function Buscar() {
  const params = useLocalSearchParams<{ q?: string }>();
  const { zona } = useZona();
  const insets = useSafeAreaInsets();
  const [texto, setTexto] = useState('');
  const [criterios, setCriterios] = useState<Criterios | null>(null);
  const [vehiculos, setVehiculos] = useState<Vehiculo[] | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guardar, setGuardar] = useState(false);
  const pedido = useRef(0);

  const ejecutar = useCallback(async (c: Criterios) => {
    const n = ++pedido.current;
    setCriterios(c);
    setCargando(true);
    setError(null);
    try {
      const lista = await api.buscarVehiculos(c);
      if (n === pedido.current) setVehiculos(lista);
    } catch (e) {
      if (n === pedido.current) setError(mensajeError(e));
    } finally {
      if (n === pedido.current) setCargando(false);
    }
  }, []);

  const buscarTexto = useCallback((t: string) => {
    setTexto(t);
    ejecutar(interpretar(t));
  }, [ejecutar]);

  useEffect(() => {
    if (params.q) buscarTexto(String(params.q));
  }, [params.q, buscarTexto]);

  const quitar = (clave: ClaveCriterio) => {
    if (!criterios) return;
    const c = quitarCriterio(criterios, clave);
    setTexto(textoDesdeCriterios(c));
    ejecutar(c);
  };

  const limpiar = () => {
    pedido.current++;
    setTexto('');
    setCriterios(null);
    setVehiculos(null);
    setError(null);
    setCargando(false);
  };

  const resultados = useMemo(() => (criterios && vehiculos ? buscar(vehiculos, criterios, zona) : null), [vehiculos, criterios, zona]);
  const desde = criterios?.lugar?.ciudad ?? zona.ciudad;

  // ─── Inicio: ilustración, título, barra, ejemplos ───
  if (!criterios) {
    return (
      <View style={{ flex: 1, backgroundColor: colores.tinta }}>
        <FondoRuta />
        <ScrollView contentContainerStyle={[estilos.inicio, { paddingTop: insets.top + 18 }]} keyboardShouldPersistTaps="handled">
          <View style={estilos.logo}>
            <View style={estilos.logoIcono}>
              <Icono nombre="campana" tam={18} color={colores.blanco} relleno />
            </View>
            <Text style={estilos.logoTexto}>Avisame</Text>
          </View>
          <Text style={estilos.titular} accessibilityRole="header">
            Decinos qué auto querés. Te avisamos cuando aparece.
          </Text>
          <BarraMatricula valor={texto} onCambio={setTexto} onBuscar={() => buscarTexto(texto)} onLimpiar={() => setTexto('')} />
          <Text style={estilos.probaTexto}>Probá con:</Text>
          <View style={estilos.ejemplos}>
            {EJEMPLOS.map((e) => (
              <Pressable key={e} accessibilityRole="button" onPress={() => buscarTexto(e)} style={({ pressed }) => [estilos.ejemplo, pressed && { opacity: 0.8 }]}>
                <Text style={estilos.ejemploTexto}>{e}</Text>
              </Pressable>
            ))}
          </View>
          <View style={{ marginTop: 18 }}>
            <SelectorZona claro />
          </View>
          <Boton titulo="📢 Publicá tu vehículo" variante="blanco" onPress={() => router.push('/publicar')} style={{ marginTop: 18, alignSelf: 'flex-start' }} />
          <Pressable accessibilityRole="link" onPress={() => buscarTexto('')} style={{ marginTop: 14, alignSelf: 'flex-start' }}>
            <Text style={estilos.verTodos}>Ver todos los vehículos →</Text>
          </Pressable>
        </ScrollView>
      </View>
    );
  }

  // ─── Resultados ───
  const secciones = resultados
    ? [
        { clave: 'coincide', titulo: `Coincide (${resultados.coinciden.length})`, data: resultados.coinciden },
        ...(resultados.casi.length
          ? [{ clave: 'casi', titulo: `Casi (${resultados.casi.length})`, ayuda: 'Parecidos a lo que buscás: te decimos qué les falta.', data: resultados.casi }]
          : []),
      ]
    : [];
  const sinCoincidencias = resultados && resultados.coinciden.length === 0;

  return (
    <View style={{ flex: 1, backgroundColor: colores.fondo }}>
      <View style={[estilos.cabecera, { paddingTop: insets.top + 10 }]}>
        <View style={estilos.ancho}>
          <BarraMatricula valor={texto} onCambio={setTexto} onBuscar={() => buscarTexto(texto)} onLimpiar={limpiar} />
          <View style={estilos.chips}>
            {etiquetas(criterios).map((e) => (
              <Pressable
                key={e.clave}
                accessibilityRole="button"
                accessibilityLabel={`Quitar ${e.texto}`}
                onPress={() => quitar(e.clave)}
                style={({ pressed }) => [estilos.chip, pressed && { opacity: 0.8 }]}
              >
                <Text style={estilos.chipTexto}>{e.texto}</Text>
                <Icono nombre="x" tam={14} color={colores.banda} />
              </Pressable>
            ))}
            {etiquetas(criterios).length === 0 ? <Text style={estilos.todos}>Todos los vehículos</Text> : null}
          </View>
          <SelectorZona claro />
        </View>
      </View>

      {cargando && !resultados ? (
        <Cargando texto="Buscando…" />
      ) : error ? (
        <View style={estilos.ancho}>
          <View style={{ padding: 16 }}>
            <Aviso tipo="error">{error}</Aviso>
            <Boton titulo="Probar de nuevo" onPress={() => ejecutar(criterios)} />
          </View>
        </View>
      ) : (
        <SectionList
          sections={secciones}
          keyExtractor={(r: Resultado<Vehiculo>) => r.vehiculo.id}
          contentContainerStyle={[estilos.lista, estilos.ancho]}
          stickySectionHeadersEnabled={false}
          keyboardShouldPersistTaps="handled"
          ListHeaderComponent={
            sinCoincidencias ? (
              <TarjetaAvisame destacada onPress={() => setGuardar(true)} hayCasi={!!resultados?.casi.length} />
            ) : null
          }
          renderSectionHeader={({ section }) =>
            section.clave === 'coincide' && section.data.length === 0 ? null : (
              <View style={estilos.seccion}>
                <Text style={[estilos.seccionTitulo, section.clave === 'casi' && { color: colores.ambar }]}>{section.titulo}</Text>
                {'ayuda' in section && section.ayuda ? <Text style={estilos.seccionAyuda}>{section.ayuda}</Text> : null}
              </View>
            )
          }
          renderItem={({ item }) => <TarjetaVehiculo v={item.vehiculo} distanciaKm={item.distanciaKm} desde={desde} motivos={item.motivos} />}
          ListFooterComponent={!sinCoincidencias ? <TarjetaAvisame onPress={() => setGuardar(true)} /> : <View style={{ height: 24 }} />}
        />
      )}

      <GuardarBusqueda visible={guardar} onCerrar={() => setGuardar(false)} texto={texto} criterios={criterios} />
    </View>
  );
}

function TarjetaAvisame({ onPress, destacada, hayCasi }: { onPress: () => void; destacada?: boolean; hayCasi?: boolean }) {
  return (
    <View style={[estilos.avisame, destacada && estilos.avisameDestacada]}>
      <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
        <View style={estilos.avisameIcono}>
          <Icono nombre="campana" color={colores.blanco} relleno />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={estilos.avisameTitulo}>
            {destacada ? 'Todavía no hay uno exacto' : '¿No es lo que buscás?'}
          </Text>
          <Text style={estilos.avisameTexto}>
            {destacada && hayCasi ? 'Mirá los parecidos abajo, o ' : ''}guardá la búsqueda y te avisamos al celular apenas alguien lo publique.
          </Text>
        </View>
      </View>
      <Boton titulo="Avisame cuando aparezca" icono="campana" onPress={onPress} style={{ marginTop: 12 }} />
    </View>
  );
}

const estilos = StyleSheet.create({
  inicio: { padding: 20, paddingBottom: 260, width: '100%', maxWidth: ANCHO_MAX, alignSelf: 'center' },
  logo: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 26 },
  logoIcono: { width: 30, height: 30, borderRadius: 8, backgroundColor: colores.banda, alignItems: 'center', justifyContent: 'center' },
  logoTexto: { fontFamily: fuentes.titulo, fontSize: 22, color: colores.blanco, letterSpacing: 0.3 },
  titular: { fontFamily: fuentes.titulo, fontSize: 36, lineHeight: 40, color: colores.blanco, marginBottom: 22, maxWidth: 520 },
  probaTexto: { fontFamily: fuentes.semi, color: 'rgba(255,255,255,0.85)', fontSize: 14, marginTop: 18, marginBottom: 8 },
  ejemplos: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  ejemplo: { backgroundColor: 'rgba(255,255,255,0.16)', borderColor: 'rgba(255,255,255,0.35)', borderWidth: 1, borderRadius: 18, paddingHorizontal: 12, paddingVertical: 8 },
  ejemploTexto: { color: colores.blanco, fontFamily: fuentes.media, fontSize: 15 },
  verTodos: { color: colores.blanco, fontFamily: fuentes.semi, fontSize: 15, textDecorationLine: 'underline' },
  cabecera: { backgroundColor: colores.tinta, paddingHorizontal: 16, paddingBottom: 12 },
  ancho: { width: '100%', maxWidth: ANCHO_MAX, alignSelf: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12, marginBottom: 10 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colores.bandaClara, borderRadius: 16, paddingLeft: 12, paddingRight: 10, minHeight: 34 },
  chipTexto: { fontFamily: fuentes.semi, fontSize: 15, color: colores.banda },
  todos: { fontFamily: fuentes.media, fontSize: 15, color: 'rgba(255,255,255,0.8)', paddingVertical: 6 },
  lista: { padding: 16, paddingBottom: 32 },
  seccion: { marginBottom: 10, marginTop: 6 },
  seccionTitulo: { fontFamily: fuentes.titulo, fontSize: 22, color: colores.verde },
  seccionAyuda: { fontFamily: fuentes.normal, fontSize: 14, color: colores.gris },
  avisame: { backgroundColor: colores.blanco, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colores.borde, marginTop: 6, marginBottom: 16 },
  avisameDestacada: { borderColor: colores.banda, borderWidth: 2 },
  avisameIcono: { width: 44, height: 44, borderRadius: 22, backgroundColor: colores.banda, alignItems: 'center', justifyContent: 'center' },
  avisameTitulo: { fontFamily: fuentes.titulo, fontSize: 20, color: colores.tinta },
  avisameTexto: { fontFamily: fuentes.normal, fontSize: 15, color: colores.gris, marginTop: 2 },
});
