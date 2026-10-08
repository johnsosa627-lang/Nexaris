import { Text, View } from 'react-native';
import { colores, fuentes } from '../tema';
import { Pantalla, Texto, Titulo } from './ui';

export type Seccion = { titulo: string; parrafos: string[] };

export function Legal({ titulo, actualizado, intro, secciones }: { titulo: string; actualizado: string; intro: string; secciones: Seccion[] }) {
  return (
    <Pantalla>
      <Titulo>{titulo}</Titulo>
      <Text style={{ fontFamily: fuentes.normal, color: colores.gris, marginTop: 4, marginBottom: 12 }}>Última actualización: {actualizado}</Text>
      <Texto>{intro}</Texto>
      {secciones.map((s, i) => (
        <View key={s.titulo} style={{ marginTop: 18 }}>
          <Titulo nivel={3}>{i + 1}. {s.titulo}</Titulo>
          {s.parrafos.map((p) => (
            <Texto key={p} style={{ marginTop: 6 }} selectable>{p}</Texto>
          ))}
        </View>
      ))}
    </Pantalla>
  );
}
