// La barra de búsqueda con forma de matrícula Mercosur.
import { useRef } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { colores, fuentes } from '../tema';
import { Icono } from './Icono';

export function BarraMatricula({
  valor, onCambio, onBuscar, onLimpiar, autoFocus,
}: { valor: string; onCambio: (t: string) => void; onBuscar: () => void; onLimpiar?: () => void; autoFocus?: boolean }) {
  const input = useRef<TextInput>(null);
  return (
    <View style={estilos.placa}>
      <View style={estilos.banda}>
        <Text style={estilos.pregunta} numberOfLines={1}>¿Qué vehículo estás buscando?</Text>
        <View style={estilos.pais}>
          <View style={estilos.sol} />
          <Text style={estilos.uy}>UY</Text>
        </View>
      </View>
      <View style={estilos.cuerpo}>
        <TextInput
          ref={input}
          value={valor}
          onChangeText={onCambio}
          onSubmitEditing={onBuscar}
          autoFocus={autoFocus}
          returnKeyType="search"
          placeholder="Ej.: Corolla automático hasta 20 mil dólares"
          placeholderTextColor={colores.grisClaro}
          accessibilityLabel="¿Qué vehículo estás buscando?"
          style={estilos.input}
          multiline={false}
        />
        {valor && onLimpiar ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Borrar búsqueda" hitSlop={10} onPress={() => { onLimpiar(); input.current?.focus(); }} style={estilos.limpiar}>
            <Icono nombre="x" tam={20} color={colores.gris} />
          </Pressable>
        ) : null}
        <Pressable accessibilityRole="button" accessibilityLabel="Buscar" onPress={onBuscar} style={({ pressed }) => [estilos.boton, pressed && { opacity: 0.85 }]}>
          <Icono nombre="buscar" tam={24} color={colores.blanco} />
        </Pressable>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  placa: {
    backgroundColor: colores.blanco, borderRadius: 12, borderWidth: 2.5, borderColor: colores.tinta, overflow: 'hidden',
    shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 6,
  },
  banda: { backgroundColor: colores.banda, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 6, gap: 8 },
  pregunta: { flex: 1, color: colores.blanco, fontFamily: fuentes.tituloSemi, fontSize: 15, letterSpacing: 0.4, textTransform: 'uppercase' },
  pais: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  sol: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#FCD34D' },
  uy: { color: colores.blanco, fontFamily: fuentes.titulo, fontSize: 16, letterSpacing: 1 },
  cuerpo: { flexDirection: 'row', alignItems: 'center', paddingLeft: 14, paddingRight: 6, paddingVertical: 6, minHeight: 62 },
  input: { flex: 1, fontFamily: fuentes.tituloSemi, fontSize: 21, color: colores.tinta, paddingVertical: 8, minWidth: 0 },
  limpiar: { padding: 8 },
  boton: { width: 48, height: 48, borderRadius: 10, backgroundColor: colores.banda, alignItems: 'center', justifyContent: 'center', marginLeft: 4 },
});
