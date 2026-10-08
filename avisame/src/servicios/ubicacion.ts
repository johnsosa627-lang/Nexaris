import * as Location from 'expo-location';
import { ciudadMasCercana, type Ubicacion } from '../nucleo';

/**
 * Ubicación aproximada del celular (no hace falta la exacta). Devuelve la
 * ciudad más cercana como nombre y las coordenadas reales para medir distancias.
 */
export async function ubicacionDelCelular(): Promise<Ubicacion> {
  const permiso = await Location.requestForegroundPermissionsAsync();
  if (!permiso.granted) {
    throw new Error('Sin permiso de ubicación. Podés elegir tu zona a mano.');
  }
  const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Low });
  const { latitude: lat, longitude: lng } = pos.coords;
  const cercana = ciudadMasCercana(lat, lng);
  return { ...cercana, lat, lng };
}
