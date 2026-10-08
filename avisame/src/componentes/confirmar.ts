import { Alert, Platform } from 'react-native';

/** Pide confirmación antes de una acción (en la web usa el diálogo del navegador). */
export function confirmar(titulo: string, mensaje: string, boton: string, accion: () => void) {
  if (Platform.OS === 'web') {
    if (window.confirm(`${titulo}\n\n${mensaje}`)) accion();
    return;
  }
  Alert.alert(titulo, mensaje, [
    { text: 'Cancelar', style: 'cancel' },
    { text: boton, style: 'destructive', onPress: accion },
  ]);
}

/** Muestra un mensaje simple. */
export function informar(titulo: string, mensaje: string) {
  if (Platform.OS === 'web') window.alert(`${titulo}\n\n${mensaje}`);
  else Alert.alert(titulo, mensaje);
}
