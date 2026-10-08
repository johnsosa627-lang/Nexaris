import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { Vehiculo } from '../datos/tipos';
import { avisoLejos, formatoNumero, formatoUSD, nombreLugar, nombreTransmision, textoDistancia } from '../nucleo';
import { colores, fuentes, radio } from '../tema';
import { FotoVehiculo } from './FotoVehiculo';
import { Icono } from './Icono';

export function TarjetaVehiculo({
  v, distanciaKm, desde, motivos, estado,
}: { v: Vehiculo; distanciaKm?: number | null; desde?: string | null; motivos?: string[]; estado?: boolean }) {
  const lejos = distanciaKm != null && desde ? avisoLejos(distanciaKm, desde) : null;
  return (
    <Link href={`/vehiculo/${v.id}`} asChild>
      <Pressable accessibilityRole="link" style={({ pressed }) => [estilos.tarjeta, v.destacado && estilos.destacada, pressed && { opacity: 0.92 }]}>
        <View>
          <FotoVehiculo uri={v.fotos[0]} style={estilos.foto} etiqueta={`${v.marca} ${v.modelo}`} />
          {v.destacado ? (
            <View style={estilos.insignia}>
              <Text style={estilos.insigniaTexto}>★ Destacado</Text>
            </View>
          ) : null}
          {estado && v.estado !== 'activo' ? (
            <View style={[estilos.insignia, { backgroundColor: colores.tinta, left: undefined, right: 10 }]}>
              <Text style={[estilos.insigniaTexto, { color: colores.blanco }]}>{v.estado === 'pausado' ? 'Pausada' : 'Vendido'}</Text>
            </View>
          ) : null}
        </View>
        <View style={estilos.cuerpo}>
          <Text style={estilos.precio}>{formatoUSD(v.precio_usd)}</Text>
          <Text style={estilos.titulo} numberOfLines={1}>
            {v.marca} {v.modelo} <Text style={estilos.version}>{v.version ?? ''}</Text>
          </Text>
          <Text style={estilos.datos}>
            {v.anio} · {formatoNumero(v.km)} km · {nombreTransmision(v.transmision)}{v.traccion_4x4 ? ' · 4x4' : ''}
          </Text>
          <View style={estilos.lugar}>
            <Icono nombre="ubicacion" tam={16} color={colores.gris} />
            <Text style={estilos.lugarTexto} numberOfLines={1}>
              {nombreLugar(v.departamento, v.ciudad)}
              {distanciaKm != null && !lejos && desde ? ` · ${textoDistancia(distanciaKm)} de ${desde}` : ''}
            </Text>
          </View>
          {lejos ? <Text style={estilos.lejos}>{lejos}</Text> : null}
          {motivos?.length ? (
            <View style={estilos.motivos}>
              {motivos.map((m) => (
                <Text key={m} style={estilos.motivo}>≈ {m}</Text>
              ))}
            </View>
          ) : null}
          {v.automotora_nombre ? <Text style={estilos.automotora}>🏪 {v.automotora_nombre}</Text> : null}
        </View>
      </Pressable>
    </Link>
  );
}

const estilos = StyleSheet.create({
  tarjeta: { backgroundColor: colores.blanco, borderRadius: radio.grande, overflow: 'hidden', borderWidth: 1, borderColor: '#E1E6ED', marginBottom: 14 },
  destacada: { borderColor: '#E9C46A', borderWidth: 2 },
  foto: { width: '100%', aspectRatio: 16 / 9 },
  insignia: { position: 'absolute', top: 10, left: 10, backgroundColor: colores.doradoFondo, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  insigniaTexto: { fontFamily: fuentes.negrita, fontSize: 13, color: colores.dorado },
  cuerpo: { padding: 14, gap: 3 },
  precio: { fontFamily: fuentes.titulo, fontSize: 24, color: colores.tinta },
  titulo: { fontFamily: fuentes.semi, fontSize: 18, color: colores.tinta },
  version: { fontFamily: fuentes.normal, color: colores.gris, fontSize: 16 },
  datos: { fontFamily: fuentes.normal, fontSize: 15, color: colores.gris },
  lugar: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  lugarTexto: { fontFamily: fuentes.media, fontSize: 15, color: colores.tinta, flex: 1 },
  lejos: { fontFamily: fuentes.semi, fontSize: 14, color: colores.naranja, backgroundColor: colores.naranjaFondo, alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, marginTop: 4 },
  motivos: { marginTop: 6, gap: 2 },
  motivo: { fontFamily: fuentes.media, fontSize: 14, color: colores.ambar },
  automotora: { fontFamily: fuentes.media, fontSize: 14, color: colores.gris, marginTop: 4 },
});
