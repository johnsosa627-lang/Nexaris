// Botón "📍 Tu zona" que abre la elección de departamento y ciudad, o la ubicación del celular.
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useZona } from '../estado/Zona';
import { DEPARTAMENTOS, nombreLugar } from '../nucleo';
import { colores, fuentes, radio } from '../tema';
import { Icono } from './Icono';
import { Aviso, Boton, Texto } from './ui';

export function SelectorZona({ claro }: { claro?: boolean }) {
  const { zona, elegir, usarCelular } = useZona();
  const insets = useSafeAreaInsets();
  const [abierto, setAbierto] = useState(false);
  const [dep, setDep] = useState<string | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cerrar = () => {
    setAbierto(false);
    setDep(null);
    setError(null);
  };
  const departamento = DEPARTAMENTOS.find((d) => d.nombre === dep);

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Tu zona: ${nombreLugar(zona.departamento, zona.ciudad)}. Cambiar`}
        onPress={() => setAbierto(true)}
        style={({ pressed }) => [estilos.boton, claro && estilos.botonClaro, pressed && { opacity: 0.85 }]}
      >
        <Icono nombre={zona.origen === 'celular' ? 'gps' : 'ubicacion'} tam={18} color={claro ? colores.blanco : colores.banda} />
        <Text style={[estilos.botonTexto, claro && { color: colores.blanco }]} numberOfLines={1}>
          {zona.origen === 'predeterminada' ? 'Elegí tu zona' : `Estás en ${nombreLugar(zona.departamento, zona.ciudad)}`}
        </Text>
        <Icono nombre="abajo" tam={16} color={claro ? colores.blanco : colores.banda} />
      </Pressable>

      <Modal visible={abierto} animationType="slide" presentationStyle="pageSheet" onRequestClose={cerrar}>
        <View style={[estilos.modal, { paddingTop: insets.top + 8 }]}>
          <View style={estilos.cabecera}>
            {dep ? (
              <Pressable accessibilityRole="button" accessibilityLabel="Volver" onPress={() => setDep(null)} hitSlop={10}>
                <Icono nombre="atras" />
              </Pressable>
            ) : null}
            <Text style={estilos.titulo}>{dep ?? '¿Dónde estás?'}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={cerrar} hitSlop={10}>
              <Icono nombre="x" />
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: insets.bottom + 24 }}>
            {!dep ? (
              <>
                <Texto style={{ color: colores.gris, marginBottom: 12 }}>
                  Te mostramos todos los vehículos del país, primero los más cercanos a tu zona.
                </Texto>
                <Boton
                    titulo="Usar la ubicación del celular"
                    icono="gps"
                    variante="claro"
                    cargando={buscando}
                    onPress={async () => {
                      setBuscando(true);
                      setError(null);
                      try {
                        await usarCelular();
                        cerrar();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : 'No pudimos obtener tu ubicación.');
                      } finally {
                        setBuscando(false);
                      }
                    }}
                    style={{ marginBottom: 8 }}
                  />
                <Texto style={estilos.nota}>Usamos solo tu ubicación aproximada, para calcular distancias. No la guardamos en el servidor.</Texto>
                {error ? <Aviso tipo="error">{error}</Aviso> : null}
                <Text style={estilos.seccion}>O elegí tu departamento</Text>
                {DEPARTAMENTOS.map((d) => (
                  <Pressable key={d.nombre} accessibilityRole="button" onPress={() => setDep(d.nombre)} style={({ pressed }) => [estilos.item, pressed && { backgroundColor: colores.fondo }]}>
                    <Text style={estilos.itemTexto}>{d.nombre}</Text>
                    <Icono nombre="flecha" tam={18} color={colores.grisClaro} />
                  </Pressable>
                ))}
              </>
            ) : (
              departamento?.ciudades.map((c) => (
                <Pressable
                  key={c.nombre}
                  accessibilityRole="button"
                  onPress={() => {
                    elegir(departamento.nombre, c.nombre);
                    cerrar();
                  }}
                  style={({ pressed }) => [estilos.item, pressed && { backgroundColor: colores.fondo }]}
                >
                  <Text style={estilos.itemTexto}>{c.nombre}</Text>
                  {zona.ciudad === c.nombre ? <Icono nombre="check" color={colores.banda} /> : null}
                </Pressable>
              ))
            )}
          </ScrollView>
        </View>
      </Modal>
    </>
  );
}

const estilos = StyleSheet.create({
  boton: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingHorizontal: 12, minHeight: 40,
    borderRadius: 20, backgroundColor: colores.blanco, borderWidth: 1, borderColor: colores.borde, maxWidth: '100%',
  },
  botonClaro: { backgroundColor: 'rgba(255,255,255,0.14)', borderColor: 'rgba(255,255,255,0.4)' },
  botonTexto: { fontFamily: fuentes.semi, fontSize: 15, color: colores.banda, flexShrink: 1 },
  modal: { flex: 1, backgroundColor: colores.blanco },
  cabecera: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 12 },
  titulo: { flex: 1, fontFamily: fuentes.titulo, fontSize: 22, color: colores.tinta },
  nota: { fontSize: 14, color: colores.gris, marginBottom: 12 },
  seccion: { fontFamily: fuentes.semi, fontSize: 15, color: colores.gris, marginTop: 8, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  item: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 15, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: colores.fondo, borderRadius: radio.chico },
  itemTexto: { fontFamily: fuentes.normal, fontSize: 17, color: colores.tinta },
});
