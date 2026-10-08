// Piezas básicas de interfaz: textos, botones, campos, opciones y contenedores.
import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ANCHO_MAX, colores, fuentes, radio } from '../tema';
import { Icono, type NombreIcono } from './Icono';

export function Texto({ children, style, numberOfLines, selectable }: { children: ReactNode; style?: StyleProp<TextStyle>; numberOfLines?: number; selectable?: boolean }) {
  return (
    <Text style={[estilos.texto, style]} numberOfLines={numberOfLines} selectable={selectable}>
      {children}
    </Text>
  );
}

export function Titulo({ children, style, nivel = 1 }: { children: ReactNode; style?: StyleProp<TextStyle>; nivel?: 1 | 2 | 3 }) {
  return (
    <Text accessibilityRole="header" style={[nivel === 1 ? estilos.h1 : nivel === 2 ? estilos.h2 : estilos.h3, style]}>
      {children}
    </Text>
  );
}

type VarianteBoton = 'primario' | 'secundario' | 'whatsapp' | 'peligro' | 'claro' | 'blanco';

export function Boton({
  titulo, onPress, variante = 'primario', icono, cargando, deshabilitado, style, chico,
}: {
  titulo: string; onPress: () => void; variante?: VarianteBoton; icono?: NombreIcono; cargando?: boolean;
  deshabilitado?: boolean; style?: StyleProp<ViewStyle>; chico?: boolean;
}) {
  const fondo = { primario: colores.banda, secundario: colores.blanco, whatsapp: colores.whatsapp, peligro: colores.blanco, claro: colores.bandaClara, blanco: colores.blanco }[variante];
  const tinta = { primario: colores.blanco, secundario: colores.tinta, whatsapp: colores.blanco, peligro: colores.rojo, claro: colores.banda, blanco: colores.banda }[variante];
  const borde = variante === 'secundario' ? colores.borde : variante === 'peligro' ? '#F1C4C4' : fondo;
  const inactivo = deshabilitado || cargando;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!inactivo, busy: !!cargando }}
      onPress={inactivo ? undefined : onPress}
      style={({ pressed }) => [
        estilos.boton,
        chico && estilos.botonChico,
        { backgroundColor: fondo, borderColor: borde, opacity: inactivo ? 0.55 : pressed ? 0.85 : 1 },
        style,
      ]}
    >
      {cargando ? <ActivityIndicator color={tinta} /> : icono ? <Icono nombre={icono} color={tinta} tam={chico ? 18 : 20} /> : null}
      <Text style={[estilos.botonTexto, chico && { fontSize: 15 }, { color: tinta }]}>{titulo}</Text>
    </Pressable>
  );
}

export function Campo({ etiqueta, ayuda, error, style, ...props }: TextInputProps & { etiqueta: string; ayuda?: string; error?: string | null }) {
  return (
    <View style={[estilos.campo, style as StyleProp<ViewStyle>]}>
      <Text style={estilos.etiqueta}>{etiqueta}</Text>
      <TextInput
        placeholderTextColor={colores.grisClaro}
        {...props}
        accessibilityLabel={etiqueta}
        style={[estilos.input, props.multiline && { minHeight: 96, textAlignVertical: 'top' }, error ? { borderColor: colores.rojo } : null]}
      />
      {error ? <Text style={estilos.error}>{error}</Text> : ayuda ? <Text style={estilos.ayuda}>{ayuda}</Text> : null}
    </View>
  );
}

/** Botones de opción (una sola elegida). */
export function Opciones<T extends string>({ etiqueta, opciones, valor, onCambio }: { etiqueta?: string; opciones: { id: T; nombre: string }[]; valor: T | null; onCambio: (v: T) => void }) {
  return (
    <View style={estilos.campo}>
      {etiqueta ? <Text style={estilos.etiqueta}>{etiqueta}</Text> : null}
      <View style={estilos.opciones} accessibilityRole="radiogroup">
        {opciones.map((o) => {
          const activa = o.id === valor;
          return (
            <Pressable
              key={o.id}
              accessibilityRole="radio"
              accessibilityState={{ selected: activa }}
              onPress={() => onCambio(o.id)}
              style={[estilos.opcion, activa && estilos.opcionActiva]}
            >
              <Text style={[estilos.opcionTexto, activa && { color: colores.blanco }]}>{o.nombre}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function Casilla({ marcada, onCambio, children }: { marcada: boolean; onCambio: (v: boolean) => void; children: ReactNode }) {
  return (
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: marcada }} onPress={() => onCambio(!marcada)} style={estilos.casilla}>
      <View style={[estilos.cuadro, marcada && { backgroundColor: colores.banda, borderColor: colores.banda }]}>
        {marcada ? <Icono nombre="check" color={colores.blanco} tam={16} /> : null}
      </View>
      <Text style={[estilos.texto, { flex: 1 }]}>{children}</Text>
    </Pressable>
  );
}

export function Tarjeta({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[estilos.tarjeta, style]}>{children}</View>;
}

/** Pantalla con scroll, ancho máximo y márgenes cómodos. */
export function Pantalla({ children, style, sinScroll, abajo }: { children: ReactNode; style?: StyleProp<ViewStyle>; sinScroll?: boolean; abajo?: ReactNode }) {
  const insets = useSafeAreaInsets();
  if (sinScroll) return <View style={[estilos.pantalla, { padding: 16 }, style]}>{children}</View>;
  return (
    <View style={estilos.pantalla}>
      <ScrollView contentContainerStyle={[estilos.contenido, { paddingBottom: 32 + (abajo ? 0 : insets.bottom) }, style]} keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
      {abajo}
    </View>
  );
}

export function Cargando({ texto }: { texto?: string }) {
  return (
    <View style={estilos.centro}>
      <ActivityIndicator color={colores.banda} size="large" />
      {texto ? <Texto style={{ marginTop: 12, color: colores.gris }}>{texto}</Texto> : null}
    </View>
  );
}

export function Vacio({ icono, titulo, texto, children }: { icono: NombreIcono; titulo: string; texto?: string; children?: ReactNode }) {
  return (
    <View style={[estilos.centro, { paddingVertical: 40 }]}>
      <View style={estilos.vacioIcono}>
        <Icono nombre={icono} tam={30} color={colores.banda} />
      </View>
      <Titulo nivel={2} style={{ textAlign: 'center', marginTop: 14 }}>{titulo}</Titulo>
      {texto ? <Texto style={{ textAlign: 'center', color: colores.gris, marginTop: 6, maxWidth: 360 }}>{texto}</Texto> : null}
      {children ? <View style={{ marginTop: 18, alignSelf: 'stretch', alignItems: 'center' }}>{children}</View> : null}
    </View>
  );
}

export function Aviso({ tipo = 'info', children }: { tipo?: 'info' | 'error' | 'ok' | 'alerta'; children: ReactNode }) {
  const c = {
    info: [colores.bandaClara, colores.banda],
    error: ['#FDE2E2', colores.rojo],
    ok: [colores.verdeFondo, colores.verde],
    alerta: [colores.naranjaFondo, colores.naranja],
  }[tipo];
  return (
    <View style={[estilos.aviso, { backgroundColor: c[0] }]} accessibilityRole={tipo === 'error' ? 'alert' : undefined}>
      <Text style={[estilos.texto, { color: c[1], fontFamily: fuentes.media }]}>{children}</Text>
    </View>
  );
}

export function Separador() {
  return <View style={{ height: 1, backgroundColor: colores.borde, marginVertical: 16 }} />;
}

export function Fila({ icono, titulo, detalle, onPress, peligro }: { icono: NombreIcono; titulo: string; detalle?: string; onPress: () => void; peligro?: boolean }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [estilos.fila, pressed && { backgroundColor: colores.fondo }]}>
      <Icono nombre={icono} color={peligro ? colores.rojo : colores.banda} />
      <View style={{ flex: 1 }}>
        <Text style={[estilos.filaTitulo, peligro && { color: colores.rojo }]}>{titulo}</Text>
        {detalle ? <Text style={estilos.ayuda}>{detalle}</Text> : null}
      </View>
      <Icono nombre="flecha" color={colores.grisClaro} tam={18} />
    </Pressable>
  );
}

export const estilos = StyleSheet.create({
  texto: { fontFamily: fuentes.normal, fontSize: 16, lineHeight: 22, color: colores.tinta },
  h1: { fontFamily: fuentes.titulo, fontSize: 30, lineHeight: 34, color: colores.tinta, letterSpacing: -0.3 },
  h2: { fontFamily: fuentes.titulo, fontSize: 22, lineHeight: 27, color: colores.tinta },
  h3: { fontFamily: fuentes.semi, fontSize: 17, lineHeight: 22, color: colores.tinta },
  boton: {
    minHeight: 50, borderRadius: radio.medio, paddingHorizontal: 18, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', gap: 8, borderWidth: 1.5,
  },
  botonChico: { minHeight: 40, paddingHorizontal: 12, borderRadius: radio.chico },
  botonTexto: { fontFamily: fuentes.semi, fontSize: 17 },
  campo: { marginBottom: 14 },
  etiqueta: { fontFamily: fuentes.semi, fontSize: 15, color: colores.tinta, marginBottom: 6 },
  input: {
    minHeight: 50, borderWidth: 1.5, borderColor: colores.borde, borderRadius: radio.medio, backgroundColor: colores.blanco,
    paddingHorizontal: 14, paddingVertical: 12, fontFamily: fuentes.normal, fontSize: 17, color: colores.tinta,
  },
  ayuda: { fontFamily: fuentes.normal, fontSize: 14, color: colores.gris, marginTop: 4 },
  error: { fontFamily: fuentes.media, fontSize: 14, color: colores.rojo, marginTop: 4 },
  opciones: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  opcion: {
    minHeight: 44, paddingHorizontal: 16, borderRadius: 22, borderWidth: 1.5, borderColor: colores.borde,
    backgroundColor: colores.blanco, justifyContent: 'center',
  },
  opcionActiva: { backgroundColor: colores.banda, borderColor: colores.banda },
  opcionTexto: { fontFamily: fuentes.media, fontSize: 16, color: colores.tinta },
  casilla: { flexDirection: 'row', gap: 12, alignItems: 'flex-start', paddingVertical: 8 },
  cuadro: {
    width: 26, height: 26, borderRadius: 6, borderWidth: 2, borderColor: colores.grisClaro, alignItems: 'center',
    justifyContent: 'center', backgroundColor: colores.blanco, marginTop: -1,
  },
  tarjeta: { backgroundColor: colores.blanco, borderRadius: radio.grande, padding: 16, borderWidth: 1, borderColor: '#E1E6ED' },
  pantalla: { flex: 1, backgroundColor: colores.fondo },
  contenido: { padding: 16, width: '100%', maxWidth: ANCHO_MAX, alignSelf: 'center' },
  centro: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  vacioIcono: { width: 64, height: 64, borderRadius: 32, backgroundColor: colores.bandaClara, alignItems: 'center', justifyContent: 'center' },
  aviso: { borderRadius: radio.medio, padding: 12, marginBottom: 14 },
  fila: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 14, paddingHorizontal: 4, borderRadius: radio.chico },
  filaTitulo: { fontFamily: fuentes.semi, fontSize: 17, color: colores.tinta },
});
