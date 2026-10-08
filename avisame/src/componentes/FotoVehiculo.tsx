// Foto de un vehículo. En la vista previa, las fotos "demo:" son ilustraciones.
import { Image } from 'expo-image';
import { useId } from 'react';
import { StyleSheet, Text, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';
import { colores, fuentes } from '../tema';

export function FotoVehiculo({ uri, style, etiqueta }: { uri: string | undefined; style?: StyleProp<ViewStyle>; etiqueta?: string }) {
  if (!uri) return <View style={[estilos.base, { backgroundColor: '#D9DEE6' }, style]} />;
  if (uri.startsWith('demo:')) {
    const [, tipo, color, vista] = uri.split(':');
    return (
      <View style={[estilos.base, style]} accessibilityLabel={etiqueta ?? 'Ilustración de ejemplo'}>
        <IlustracionAuto tipo={tipo} color={color} interior={vista === 'interior'} />
        <Text style={estilos.marca}>Imagen de ejemplo</Text>
      </View>
    );
  }
  return <Image source={{ uri }} style={[estilos.base as ImageStyle, style as StyleProp<ImageStyle>]} contentFit="cover" transition={150} accessibilityLabel={etiqueta} />;
}

// Perfil lateral según la carrocería: [inicio techo, fin techo, alto techo, fin cola, alto cola].
const PERFILES: Record<string, { techo: [number, number, number]; cola: [number, number]; caja?: boolean }> = {
  sedan: { techo: [138, 222, 72], cola: [318, 104] },
  hatch: { techo: [130, 240, 70], cola: [300, 96] },
  suv: { techo: [124, 266, 56], cola: [314, 84] },
  pickup: { techo: [118, 196, 60], cola: [322, 98], caja: true },
  utilitario: { techo: [96, 300, 48], cola: [316, 52] },
  otro: { techo: [128, 252, 62], cola: [312, 92] },
};

function IlustracionAuto({ tipo, color, interior }: { tipo: string; color: string; interior: boolean }) {
  // En la web, los ids de los degradados tienen que ser únicos en la página.
  const id = 'f' + useId().replace(/[^a-zA-Z0-9]/g, '');
  const p = PERFILES[tipo] ?? PERFILES.otro;
  const [t1, t2, ty] = p.techo;
  const [cx, cy] = p.cola;
  // Carrocería: paragolpes delantero, capó, parabrisas, techo, luneta y cola.
  const cuerpo = p.caja
    ? `M36 150 L 38 122 Q 40 108 60 106 L ${t1 - 30} 104 L ${t1} ${ty} L ${t2} ${ty} L ${t2 + 8} 106 L ${cx} 106 L ${cx + 2} 150 Z`
    : `M36 150 L 38 124 Q 40 110 62 108 L ${t1 - 34} 104 L ${t1} ${ty} L ${t2} ${ty} L ${cx - 8} ${cy} Q ${cx + 4} ${cy + 4} ${cx + 4} 120 L ${cx + 4} 150 Z`;
  const ventanas = `M${t1 + 6} ${ty + 6} L ${t2 - 4} ${ty + 6} L ${(p.caja ? t2 + 2 : t2 + (cx - 8 - t2) * 0.55)} 102 L ${t1 - 24} 102 Z`;
  const parante = (t1 + t2) / 2;
  return (
    <Svg width="100%" height="100%" viewBox="0 0 360 200" preserveAspectRatio="xMidYMid slice">
      <Defs>
        <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={interior ? '#2B3247' : '#C9D3E3'} />
          <Stop offset="1" stopColor={interior ? '#141826' : '#EEF2F7'} />
        </LinearGradient>
      </Defs>
      <Rect x="0" y="0" width="360" height="200" fill={`url(#${id})`} />
      {interior ? (
        <>
          <Rect x="0" y="40" width="360" height="40" fill="#1C2233" />
          <Circle cx="120" cy="118" r="42" stroke="#9AA3B8" strokeWidth="9" fill="none" />
          <Rect x="114" y="112" width="12" height="44" rx="4" fill="#9AA3B8" />
          <Rect x="196" y="86" width="116" height="58" rx="10" fill="#3B455E" />
          <Rect x="206" y="96" width="96" height="38" rx="4" fill={color} opacity="0.55" />
          <Rect x="0" y="164" width="360" height="36" fill="#0E1220" />
        </>
      ) : (
        <>
          <Rect x="0" y="160" width="360" height="40" fill="#AEB8C8" />
          <Rect x="0" y="174" width="360" height="3" fill="#F3F4F6" opacity="0.7" />
          <Path d={cuerpo} fill={color} stroke="#14213D" strokeWidth="3" strokeLinejoin="round" />
          <Path d={ventanas} fill="#BFD3EA" stroke="#14213D" strokeWidth="2.5" strokeLinejoin="round" />
          <Path d={`M${parante} ${ty + 4} L ${parante} 102`} stroke="#14213D" strokeWidth="5" />
          {p.caja ? <Path d={`M${t2 + 14} 112 L ${cx - 4} 112`} stroke="#14213D" strokeWidth="2" strokeOpacity="0.5" /> : null}
          <Path d="M40 132 H 316" stroke="#14213D" strokeOpacity="0.2" strokeWidth="2" />
          <Rect x="40" y="114" width="14" height="7" rx="3" fill="#FDE68A" stroke="#14213D" strokeWidth="1.5" />
          <Rect x={cx - 8} y="112" width="10" height="9" rx="2" fill="#EF4444" stroke="#14213D" strokeWidth="1.5" />
          <Circle cx="96" cy="150" r="23" fill="#1F2433" />
          <Circle cx="96" cy="150" r="10" fill="#9CA3AF" />
          <Circle cx={cx - 46} cy="150" r="23" fill="#1F2433" />
          <Circle cx={cx - 46} cy="150" r="10" fill="#9CA3AF" />
        </>
      )}
    </Svg>
  );
}

const estilos = StyleSheet.create({
  base: { backgroundColor: '#D9DEE6', overflow: 'hidden' },
  marca: {
    position: 'absolute', right: 8, bottom: 6, fontFamily: fuentes.media, fontSize: 11, color: colores.tinta,
    backgroundColor: 'rgba(255,255,255,0.75)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4,
  },
});
