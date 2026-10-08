import type { SupabaseClient } from '@supabase/supabase-js';
import { File } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';
import { Platform } from 'react-native';
import { MAX_FOTOS } from '../nucleo';

/** Achica la foto (lado mayor 1600 px, JPEG) para que suba rápido. */
async function comprimir(uri: string): Promise<string> {
  try {
    const ref = await ImageManipulator.manipulate(uri).resize({ width: 1600 }).renderAsync();
    const r = await ref.saveAsync({ compress: 0.72, format: SaveFormat.JPEG });
    return r.uri;
  } catch {
    return uri;
  }
}

/** Sube una foto local a la carpeta del usuario y devuelve su URL pública. */
export async function subirFoto(sb: SupabaseClient, bucket: string, ruta: string, uri: string): Promise<string> {
  const lista = await comprimir(uri);
  const cuerpo = Platform.OS === 'web' ? await (await fetch(lista)).blob() : await new File(lista).arrayBuffer();
  const { error } = await sb.storage.from(bucket).upload(ruta, cuerpo, { contentType: 'image/jpeg', upsert: true });
  if (error) throw new Error('No pudimos subir una foto. Revisá tu conexión.');
  return sb.storage.from(bucket).getPublicUrl(ruta).data.publicUrl;
}

/** Elige fotos de la galería. Devuelve URIs locales (o [] si cancela). */
export async function elegirDeGaleria(yaHay: number): Promise<string[]> {
  const lugar = MAX_FOTOS - yaHay;
  if (lugar <= 0) return [];
  const r = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsMultipleSelection: true,
    selectionLimit: lugar,
    quality: 0.9,
  });
  if (r.canceled) return [];
  return r.assets.slice(0, lugar).map((a) => a.uri);
}

/** Saca una foto con la cámara. Devuelve null si no hay permiso o cancela. */
export async function sacarFoto(): Promise<string | null> {
  const permiso = await ImagePicker.requestCameraPermissionsAsync();
  if (!permiso.granted) return null;
  const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.9 });
  if (r.canceled) return null;
  return r.assets[0]?.uri ?? null;
}
