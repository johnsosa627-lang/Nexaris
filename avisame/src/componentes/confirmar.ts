import { Alert, Platform } from 'react-native';

/** Pide confirmación antes de una acción (en la web usa el diálogo del navegador). */
export function confirmar(titulo: string, mensaje: string, boton: string, accion: () => void) {
  if (Platform.OS === 'web') {
    // Dentro de un marco (la vista previa publicada) el navegador bloquea confirm(): se sigue directo.
    if (window.self !== window.top || window.confirm(`${titulo}\n\n${mensaje}`)) accion();
    return;
  }
  Alert.alert(titulo, mensaje, [
    { text: 'Cancelar', style: 'cancel' },
    { text: boton, style: 'destructive', onPress: accion },
  ]);
}
