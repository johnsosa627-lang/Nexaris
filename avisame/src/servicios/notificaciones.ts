import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import { Platform } from 'react-native';
import { api } from '../datos/api';

// Las notificaciones se muestran también con la app abierta.
if (Platform.OS !== 'web') {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
  });
}

/**
 * Pide permiso (si corresponde), obtiene el token de Expo y lo guarda en el
 * perfil. Devuelve true si quedaron activadas.
 */
export async function activarNotificaciones({ pedirPermiso }: { pedirPermiso: boolean }): Promise<boolean> {
  if (Platform.OS === 'web' || !Device.isDevice || api.vistaPrevia) return false;
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('avisos', {
      name: 'Avisos de vehículos y clientes',
      importance: Notifications.AndroidImportance.HIGH,
      lightColor: '#1E3A8A',
    });
  }
  let { status } = await Notifications.getPermissionsAsync();
  if (status !== 'granted' && pedirPermiso) status = (await Notifications.requestPermissionsAsync()).status;
  if (status !== 'granted') return false;
  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  if (!projectId) return false;
  const { data } = await Notifications.getExpoPushTokenAsync({ projectId });
  await api.guardarPushToken(data);
  return true;
}

/** Al tocar una notificación se abre el vehículo, las alertas o el panel. */
export function escucharToques(): () => void {
  if (Platform.OS === 'web') return () => {};
  const abrir = (datos: Record<string, unknown> | undefined) => {
    if (!datos) return;
    if (datos.tipo === 'alerta' && typeof datos.vehiculo_id === 'string') router.push(`/vehiculo/${datos.vehiculo_id}`);
    else if (datos.tipo === 'cliente') router.push('/automotora?pestana=clientes');
    else if (datos.tipo === 'plan') router.push('/automotora?pestana=plan');
  };
  const ultima = Notifications.getLastNotificationResponse();
  if (ultima) abrir(ultima.notification.request.content.data);
  const sub = Notifications.addNotificationResponseReceivedListener((r) => abrir(r.notification.request.content.data));
  return () => sub.remove();
}
