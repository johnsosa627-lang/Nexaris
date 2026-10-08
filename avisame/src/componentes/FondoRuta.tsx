// Ilustración de la pantalla de inicio: ruta costera al atardecer, con un auto
// de espaldas. Dibujada en SVG (pesa poco y se ve nítida en cualquier pantalla).
import { StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, Ellipse, G, LinearGradient, Path, RadialGradient, Rect, Stop } from 'react-native-svg';

export function FondoRuta() {
  // Líneas punteadas del centro: más grandes cuanto más cerca.
  const guiones = [
    [392, 396, 0.6], [404, 412, 1], [422, 436, 1.6], [452, 474, 2.4], [500, 534, 3.4], [572, 622, 4.6],
  ];
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Svg width="100%" height="100%" viewBox="0 0 400 760" preserveAspectRatio="xMidYMax slice">
        <Defs>
          <LinearGradient id="cielo" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#14213D" />
            <Stop offset="0.38" stopColor="#3E3A75" />
            <Stop offset="0.62" stopColor="#B4567A" />
            <Stop offset="0.8" stopColor="#EE8A5B" />
            <Stop offset="1" stopColor="#F9C377" />
          </LinearGradient>
          <RadialGradient id="brillo" cx="0.5" cy="0.5" r="0.5">
            <Stop offset="0" stopColor="#FFE3A3" stopOpacity="0.95" />
            <Stop offset="0.45" stopColor="#FFC27A" stopOpacity="0.45" />
            <Stop offset="1" stopColor="#FF9F6B" stopOpacity="0" />
          </RadialGradient>
          <LinearGradient id="mar" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#5B4F8E" />
            <Stop offset="1" stopColor="#1E2A57" />
          </LinearGradient>
          <LinearGradient id="ruta" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#4A4466" />
            <Stop offset="1" stopColor="#1A1D2E" />
          </LinearGradient>
          <LinearGradient id="tierra" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#3A2E5C" />
            <Stop offset="1" stopColor="#141A33" />
          </LinearGradient>
          <LinearGradient id="sombra" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#0B1430" stopOpacity="0.55" />
            <Stop offset="0.45" stopColor="#0B1430" stopOpacity="0.15" />
            <Stop offset="1" stopColor="#0B1430" stopOpacity="0" />
          </LinearGradient>
          <RadialGradient id="luzFreno" cx="0.5" cy="0.5" r="0.5">
            <Stop offset="0" stopColor="#FF4D4D" stopOpacity="0.9" />
            <Stop offset="1" stopColor="#FF4D4D" stopOpacity="0" />
          </RadialGradient>
        </Defs>

        {/* Cielo y sol */}
        <Rect x="0" y="0" width="400" height="400" fill="url(#cielo)" />
        <Circle cx="292" cy="372" r="120" fill="url(#brillo)" />
        <Circle cx="292" cy="372" r="40" fill="#FFD99A" />
        {/* Nubes finas */}
        <Path d="M20 250 h120 M60 262 h90 M250 220 h110 M280 232 h70" stroke="#F7B9A0" strokeOpacity="0.35" strokeWidth="3" strokeLinecap="round" />

        {/* Mar a la izquierda, con el reflejo del sol */}
        <Rect x="0" y="380" width="400" height="380" fill="url(#mar)" />
        <G stroke="#FFD08A" strokeLinecap="round" strokeOpacity="0.7">
          <Path d="M250 392 h70" strokeWidth="2.5" />
          <Path d="M240 404 h80" strokeWidth="2" strokeOpacity="0.5" />
          <Path d="M232 418 h70" strokeWidth="2" strokeOpacity="0.35" />
        </G>

        {/* Costa y lomas a la derecha */}
        <Path d="M190 381 C 240 372, 300 366, 400 360 L 400 760 L 245 760 Z" fill="url(#tierra)" />
        <Path d="M300 368 C 330 352, 360 350, 400 344 L 400 372 L 300 372 Z" fill="#2B2350" />

        {/* Ruta */}
        <Path d="M212 384 L 222 384 L 400 700 L 400 760 L 40 760 Z" fill="url(#ruta)" />
        <Path d="M212 384 L 40 760" stroke="#F5E6C8" strokeWidth="2.5" strokeOpacity="0.7" />
        <Path d="M222 384 L 400 700" stroke="#F5E6C8" strokeWidth="2.5" strokeOpacity="0.7" />
        {guiones.map(([y1, y2, w], i) => {
          // El centro de la ruta va de x=217 (horizonte) a x=220 (abajo).
          const x = (y: number) => 217 + ((y - 384) / 376) * 3;
          return <Path key={i} d={`M${x(y1)} ${y1} L ${x(y2)} ${y2}`} stroke="#FCE7B2" strokeWidth={w} strokeLinecap="round" />;
        })}
        {/* Postes de la costa */}
        <G stroke="#1A1D2E" strokeWidth="3" strokeLinecap="round">
          <Path d="M300 430 v18" /><Path d="M330 480 v26" /><Path d="M370 548 v36" />
        </G>

        {/* Auto de espaldas */}
        <G>
          <Ellipse cx="200" cy="702" rx="96" ry="12" fill="#0A0D1A" opacity="0.6" />
          <Circle cx="138" cy="706" r="40" fill="url(#luzFreno)" />
          <Circle cx="262" cy="706" r="40" fill="url(#luzFreno)" />
          {/* ruedas */}
          <Rect x="118" y="676" width="30" height="34" rx="6" fill="#0B0E19" />
          <Rect x="252" y="676" width="30" height="34" rx="6" fill="#0B0E19" />
          {/* carrocería */}
          <Path d="M128 650 C 132 626, 146 604, 166 596 L 234 596 C 254 604, 268 626, 272 650 Z" fill="#22305E" />
          <Path d="M150 646 C 154 630, 162 616, 174 610 L 226 610 C 238 616, 246 630, 250 646 Z" fill="#7F86B8" opacity="0.85" />
          <Path d="M174 610 L 226 610 L 216 626 L 184 626 Z" fill="#FFD08A" opacity="0.25" />
          <Rect x="112" y="648" width="176" height="44" rx="12" fill="#1B2550" />
          {/* luces traseras */}
          <Rect x="118" y="656" width="40" height="11" rx="4" fill="#FF5A4E" />
          <Rect x="242" y="656" width="40" height="11" rx="4" fill="#FF5A4E" />
          <Rect x="158" y="659" width="84" height="4" rx="2" fill="#FF7A5C" opacity="0.8" />
          {/* matrícula Mercosur */}
          <Rect x="178" y="670" width="44" height="15" rx="2" fill="#FFFFFF" />
          <Rect x="178" y="670" width="44" height="4" rx="1" fill="#1E3A8A" />
          <Rect x="184" y="677" width="32" height="2.5" rx="1" fill="#14213D" />
        </G>

        {/* Oscurece arriba para que el texto se lea bien */}
        <Rect x="0" y="0" width="400" height="520" fill="url(#sombra)" />
      </Svg>
    </View>
  );
}
