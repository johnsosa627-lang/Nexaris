// Campo que abre una lista para elegir (con buscador si la lista es larga).
import { useMemo, useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { normalizar } from '../nucleo';
import { colores, fuentes, radio } from '../tema';
import { Icono } from './Icono';
import { estilos as ui } from './ui';

export function Selector({
  etiqueta, valor, opciones, onCambio, placeholder = 'Elegir', error, conOtro,
}: {
  etiqueta: string; valor: string; opciones: string[]; onCambio: (v: string) => void; placeholder?: string;
  error?: string | null; conOtro?: boolean;
}) {
  const [abierto, setAbierto] = useState(false);
  return (
    <View style={ui.campo}>
      <Text style={ui.etiqueta}>{etiqueta}</Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${etiqueta}: ${valor || placeholder}`}
        onPress={() => setAbierto(true)}
        style={[ui.input, estilos.campo, error ? { borderColor: colores.rojo } : null]}
      >
        <Text style={[estilos.valor, !valor && { color: colores.grisClaro }]} numberOfLines={1}>{valor || placeholder}</Text>
        <Icono nombre="abajo" tam={18} color={colores.gris} />
      </Pressable>
      {error ? <Text style={ui.error}>{error}</Text> : null}
      <ListaModal
        visible={abierto}
        titulo={etiqueta}
        opciones={opciones}
        conOtro={conOtro}
        onCerrar={() => setAbierto(false)}
        onElegir={(v) => {
          onCambio(v);
          setAbierto(false);
        }}
      />
    </View>
  );
}

export function ListaModal({
  visible, titulo, opciones, onElegir, onCerrar, conOtro,
}: { visible: boolean; titulo: string; opciones: string[]; onElegir: (v: string) => void; onCerrar: () => void; conOtro?: boolean }) {
  const insets = useSafeAreaInsets();
  const [filtro, setFiltro] = useState('');
  const lista = useMemo(() => {
    const f = normalizar(filtro);
    const base = f ? opciones.filter((o) => normalizar(o).includes(f)) : opciones;
    // "Otro": lo que escribió la persona, si no está en el catálogo.
    if (conOtro && filtro.trim() && !opciones.some((o) => normalizar(o) === f)) return [...base, `__otro__${filtro.trim()}`];
    return base;
  }, [filtro, opciones, conOtro]);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onCerrar} presentationStyle="pageSheet">
      <View style={[estilos.modal, { paddingTop: insets.top + 8, paddingBottom: insets.bottom }]}>
        <View style={estilos.cabecera}>
          <Text style={estilos.titulo}>{titulo}</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={onCerrar} hitSlop={10}>
            <Icono nombre="x" />
          </Pressable>
        </View>
        {opciones.length > 8 || conOtro ? (
          <TextInput
            value={filtro}
            onChangeText={setFiltro}
            placeholder={conOtro ? 'Buscar o escribir otro…' : 'Buscar…'}
            placeholderTextColor={colores.grisClaro}
            style={[ui.input, { marginHorizontal: 16, marginBottom: 8 }]}
            autoFocus
          />
        ) : null}
        <FlatList
          data={lista}
          keyExtractor={(x) => x}
          keyboardShouldPersistTaps="handled"
          renderItem={({ item }) => {
            const otro = item.startsWith('__otro__');
            const texto = otro ? item.slice(8) : item;
            return (
              <Pressable accessibilityRole="button" onPress={() => { onElegir(texto); setFiltro(''); }} style={({ pressed }) => [estilos.item, pressed && { backgroundColor: colores.fondo }]}>
                <Text style={estilos.itemTexto}>{otro ? `Otro: “${texto}”` : texto}</Text>
              </Pressable>
            );
          }}
          ListEmptyComponent={<Text style={[estilos.itemTexto, { padding: 16, color: colores.gris }]}>No hay resultados.</Text>}
        />
      </View>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  campo: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  valor: { fontFamily: fuentes.normal, fontSize: 17, color: colores.tinta, flex: 1 },
  modal: { flex: 1, backgroundColor: colores.blanco },
  cabecera: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  titulo: { fontFamily: fuentes.titulo, fontSize: 22, color: colores.tinta },
  item: { paddingHorizontal: 16, paddingVertical: 15, borderBottomWidth: 1, borderBottomColor: colores.fondo, borderRadius: radio.chico },
  itemTexto: { fontFamily: fuentes.normal, fontSize: 17, color: colores.tinta },
});
