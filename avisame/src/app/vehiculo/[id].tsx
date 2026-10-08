// Ficha del vehículo: galería, datos, ubicación, contacto y acciones del dueño.
import { router, Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Linking, Modal, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { confirmar } from '../../componentes/confirmar';
import { FotoVehiculo } from '../../componentes/FotoVehiculo';
import { Icono } from '../../componentes/Icono';
import { Aviso, Boton, Campo, Cargando, Opciones, Tarjeta, Texto, Titulo, Vacio } from '../../componentes/ui';
import { api, mensajeError } from '../../datos/api';
import type { MotivoDenuncia, Vehiculo } from '../../datos/tipos';
import { useSesion } from '../../estado/Sesion';
import { useZona } from '../../estado/Zona';
import {
  avisoLejos,
  distanciaA,
  formatoNumero,
  formatoUSD,
  nombreCombustible,
  nombreLugar,
  nombreTipo,
  nombreTransmision,
  normalizarWhatsapp,
  textoDistancia,
} from '../../nucleo';
import { ANCHO_MAX, colores, fuentes, radio } from '../../tema';

export default function FichaVehiculo() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { usuario } = useSesion();
  const { zona } = useZona();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const [v, setV] = useState<Vehiculo | null | undefined>(undefined);
  const [foto, setFoto] = useState(0);
  const [denunciar, setDenunciar] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trabajando, setTrabajando] = useState(false);

  const cargar = useCallback(() => {
    api.vehiculo(String(id)).then(setV).catch(() => setV(null));
  }, [id]);
  useFocusEffect(cargar);

  if (v === undefined) return <Cargando />;
  if (v === null) {
    return (
      <Vacio icono="auto" titulo="Esta publicación no está disponible" texto="Puede que se haya vendido o que el dueño la haya pausado.">
        <Boton titulo="Volver a buscar" icono="buscar" onPress={() => router.navigate('/')} />
      </Vacio>
    );
  }

  const ancho = Math.min(width, ANCHO_MAX);
  const esDuenio = !!usuario && usuario.id === v.owner_id;
  const distancia = distanciaA(zona, v);
  const lejos = avisoLejos(distancia, zona.ciudad);
  const wa = normalizarWhatsapp(v.contacto_whatsapp);
  const tel = v.contacto_whatsapp.replace(/[^\d+]/g, '');
  const titulo = `${v.marca} ${v.modelo} ${v.anio}`;
  const mapa = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
    v.direccion ? `${v.direccion}, ${v.ciudad}, ${v.departamento}, Uruguay` : `${v.lat},${v.lng}`,
  )}`;

  const accion = async (f: () => Promise<void>, despues?: () => void) => {
    setTrabajando(true);
    setError(null);
    try {
      await f();
      despues ? despues() : cargar();
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setTrabajando(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colores.fondo }}>
      <Stack.Screen options={{ title: `${v.marca} ${v.modelo}` }} />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 + insets.bottom }}>
        <View style={[estilos.ancho, { width: ancho }]}>
          {/* Galería */}
          <ScrollView
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            onMomentumScrollEnd={(e) => setFoto(Math.round(e.nativeEvent.contentOffset.x / ancho))}
            onScroll={(e) => setFoto(Math.round(e.nativeEvent.contentOffset.x / ancho))}
            scrollEventThrottle={64}
          >
            {v.fotos.map((f, i) => (
              <FotoVehiculo key={f + i} uri={f} style={{ width: ancho, height: (ancho * 3) / 4 }} etiqueta={`${titulo}, foto ${i + 1} de ${v.fotos.length}`} />
            ))}
          </ScrollView>
          {v.fotos.length > 1 ? (
            <View style={estilos.contador}>
              <Text style={estilos.contadorTexto}>{foto + 1} / {v.fotos.length}</Text>
            </View>
          ) : null}
          {v.destacado ? (
            <View style={estilos.insignia}>
              <Text style={estilos.insigniaTexto}>★ Destacado</Text>
            </View>
          ) : null}

          <View style={{ padding: 16 }}>
            {v.estado !== 'activo' ? <Aviso tipo="alerta">{v.estado === 'pausado' ? 'Publicación pausada: no aparece en las búsquedas.' : 'Marcado como vendido: no aparece en las búsquedas.'}</Aviso> : null}
            <Text style={estilos.precio}>{formatoUSD(v.precio_usd)}</Text>
            <Titulo>{titulo}</Titulo>
            {v.version ? <Texto style={{ color: colores.gris, fontSize: 18 }}>{v.version}</Texto> : null}

            <View style={estilos.datos}>
              <Dato nombre="Año" valor={String(v.anio)} />
              <Dato nombre="Kilómetros" valor={`${formatoNumero(v.km)} km`} />
              <Dato nombre="Transmisión" valor={nombreTransmision(v.transmision)} />
              <Dato nombre="Combustible" valor={nombreCombustible(v.combustible)} />
              <Dato nombre="Tipo" valor={nombreTipo(v.tipo)} />
              <Dato nombre="Tracción" valor={v.traccion_4x4 ? '4x4' : '4x2'} />
            </View>

            <Tarjeta style={{ marginTop: 16 }}>
              <Text style={estilos.lugar}>📍 {nombreLugar(v.departamento, v.ciudad)}</Text>
              {v.direccion ? <Texto style={{ color: colores.gris }}>{v.direccion}</Texto> : null}
              {lejos ? (
                <Text style={estilos.lejos}>{lejos}</Text>
              ) : (
                <Texto style={{ color: colores.gris, marginTop: 2 }}>{textoDistancia(distancia)} de {zona.ciudad}</Texto>
              )}
              <Boton titulo="Ver en el mapa" icono="mapa" variante="claro" chico onPress={() => Linking.openURL(mapa)} style={{ marginTop: 12, alignSelf: 'flex-start' }} />
            </Tarjeta>

            {v.descripcion ? (
              <View style={{ marginTop: 18 }}>
                <Titulo nivel={3}>Descripción</Titulo>
                <Texto style={{ marginTop: 6 }} selectable>{v.descripcion}</Texto>
              </View>
            ) : null}

            <Tarjeta style={{ marginTop: 18 }}>
              <Text style={estilos.vende}>{v.automotora_id ? 'Automotora' : 'Vende'}</Text>
              <Text style={estilos.vendedor}>{v.automotora_id ? '🏪 ' : ''}{v.contacto_nombre}</Text>
              {!esDuenio ? (
                <View style={{ gap: 10, marginTop: 12 }}>
                  {wa && wa.startsWith('5989') ? (
                    <Boton
                      titulo="Escribir por WhatsApp"
                      icono="whatsapp"
                      variante="whatsapp"
                      onPress={() => Linking.openURL(`https://wa.me/${wa}?text=${encodeURIComponent(`Hola, vi tu ${titulo} en Avisame. ¿Sigue disponible?`)}`)}
                    />
                  ) : null}
                  <Boton titulo={`Llamar · ${v.contacto_whatsapp}`} icono="telefono" variante="secundario" onPress={() => Linking.openURL(`tel:${tel}`)} />
                </View>
              ) : null}
              {v.external_url ? (
                <Boton titulo="Ver la publicación original" variante="secundario" chico onPress={() => Linking.openURL(v.external_url!)} style={{ marginTop: 10 }} />
              ) : null}
            </Tarjeta>

            {error ? <View style={{ marginTop: 12 }}><Aviso tipo="error">{error}</Aviso></View> : null}

            {esDuenio ? (
              <View style={{ marginTop: 18, gap: 10 }}>
                <Titulo nivel={3}>Tu publicación</Titulo>
                <Boton titulo="Editar" icono="editar" variante="claro" onPress={() => router.push(`/editar/${v.id}`)} />
                {v.estado === 'activo' ? (
                  <Boton titulo="Pausar" icono="pausa" variante="secundario" cargando={trabajando} onPress={() => accion(() => api.cambiarEstado(v.id, 'pausado'))} />
                ) : (
                  <Boton titulo="Volver a publicar" icono="play" variante="secundario" cargando={trabajando} onPress={() => accion(() => api.cambiarEstado(v.id, 'activo'))} />
                )}
                {v.estado !== 'vendido' ? (
                  <Boton titulo="Marcar como vendido" icono="check" variante="secundario" onPress={() => accion(() => api.cambiarEstado(v.id, 'vendido'))} />
                ) : null}
                <Boton
                  titulo="Borrar publicación"
                  icono="basura"
                  variante="peligro"
                  onPress={() =>
                    confirmar('Borrar publicación', 'Se borra la publicación y sus fotos. No se puede deshacer.', 'Borrar', () =>
                      accion(() => api.borrarVehiculo(v.id), () => (router.canGoBack() ? router.back() : router.replace('/'))),
                    )
                  }
                />
              </View>
            ) : (
              <Pressable accessibilityRole="button" onPress={() => setDenunciar(true)} style={estilos.denunciar}>
                <Icono nombre="bandera" tam={18} color={colores.gris} />
                <Text style={estilos.denunciarTexto}>Denunciar publicación</Text>
              </Pressable>
            )}
          </View>
        </View>
      </ScrollView>
      <Denuncia visible={denunciar} vehiculoId={v.id} onCerrar={() => setDenunciar(false)} />
    </View>
  );
}

function Dato({ nombre, valor }: { nombre: string; valor: string }) {
  return (
    <View style={estilos.dato}>
      <Text style={estilos.datoNombre}>{nombre}</Text>
      <Text style={estilos.datoValor}>{valor}</Text>
    </View>
  );
}

const MOTIVOS: { id: MotivoDenuncia; nombre: string }[] = [
  { id: 'estafa', nombre: 'Posible estafa' },
  { id: 'datos_falsos', nombre: 'Datos falsos' },
  { id: 'vendido', nombre: 'Ya se vendió' },
  { id: 'ofensivo', nombre: 'Contenido ofensivo' },
  { id: 'otro', nombre: 'Otro' },
];

function Denuncia({ visible, vehiculoId, onCerrar }: { visible: boolean; vehiculoId: string; onCerrar: () => void }) {
  const insets = useSafeAreaInsets();
  const [motivo, setMotivo] = useState<MotivoDenuncia | null>(null);
  const [detalle, setDetalle] = useState('');
  const [estado, setEstado] = useState<'form' | 'enviando' | 'listo'>('form');
  const [error, setError] = useState<string | null>(null);

  const cerrar = () => {
    onCerrar();
    setEstado('form');
    setMotivo(null);
    setDetalle('');
    setError(null);
  };
  const enviar = async () => {
    if (!motivo) return setError('Elegí un motivo.');
    setEstado('enviando');
    try {
      await api.denunciar(vehiculoId, motivo, detalle);
      setEstado('listo');
    } catch (e) {
      setError(mensajeError(e));
      setEstado('form');
    }
  };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={cerrar}>
      <ScrollView style={{ backgroundColor: colores.fondo }} contentContainerStyle={{ padding: 16, paddingTop: insets.top + 16 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 12 }}>
          <Titulo nivel={2} style={{ flex: 1 }}>Denunciar publicación</Titulo>
          <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={cerrar} hitSlop={10}>
            <Icono nombre="x" />
          </Pressable>
        </View>
        {estado === 'listo' ? (
          <>
            <Aviso tipo="ok">Gracias. Revisamos las denuncias y damos de baja lo que no cumple los términos.</Aviso>
            <Boton titulo="Cerrar" onPress={cerrar} />
          </>
        ) : (
          <>
            <Opciones etiqueta="¿Qué pasa con esta publicación?" opciones={MOTIVOS} valor={motivo} onCambio={setMotivo} />
            <Campo etiqueta="Contanos más (opcional)" value={detalle} onChangeText={setDetalle} multiline maxLength={500} />
            {error ? <Aviso tipo="error">{error}</Aviso> : null}
            <Boton titulo="Enviar denuncia" icono="bandera" onPress={enviar} cargando={estado === 'enviando'} />
            <Texto style={{ color: colores.gris, fontSize: 14, marginTop: 12 }}>
              Si fuiste víctima de una estafa, hacé también la denuncia en la Policía (Ministerio del Interior).
            </Texto>
          </>
        )}
      </ScrollView>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  ancho: { alignSelf: 'center', maxWidth: ANCHO_MAX },
  contador: { position: 'absolute', right: 12, top: 12, backgroundColor: 'rgba(20,33,61,0.75)', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 3 },
  contadorTexto: { color: colores.blanco, fontFamily: fuentes.semi, fontSize: 14 },
  insignia: { position: 'absolute', left: 12, top: 12, backgroundColor: colores.doradoFondo, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  insigniaTexto: { fontFamily: fuentes.negrita, fontSize: 14, color: colores.dorado },
  precio: { fontFamily: fuentes.titulo, fontSize: 32, color: colores.banda },
  datos: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 14 },
  dato: { backgroundColor: colores.blanco, borderRadius: radio.medio, paddingHorizontal: 12, paddingVertical: 10, minWidth: '31%', flexGrow: 1, borderWidth: 1, borderColor: '#E1E6ED' },
  datoNombre: { fontFamily: fuentes.normal, fontSize: 13, color: colores.gris },
  datoValor: { fontFamily: fuentes.semi, fontSize: 17, color: colores.tinta },
  lugar: { fontFamily: fuentes.semi, fontSize: 18, color: colores.tinta },
  lejos: { fontFamily: fuentes.semi, fontSize: 15, color: colores.naranja, backgroundColor: colores.naranjaFondo, alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, marginTop: 6 },
  vende: { fontFamily: fuentes.semi, fontSize: 13, color: colores.gris, textTransform: 'uppercase', letterSpacing: 0.5 },
  vendedor: { fontFamily: fuentes.titulo, fontSize: 22, color: colores.tinta, marginTop: 2 },
  denunciar: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'center', marginTop: 24, padding: 10 },
  denunciarTexto: { fontFamily: fuentes.media, fontSize: 15, color: colores.gris, textDecorationLine: 'underline' },
});
