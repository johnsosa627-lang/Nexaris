// "Avisame cuando aparezca": guarda la búsqueda y activa los avisos al celular.
import { router } from 'expo-router';
import { useState } from 'react';
import { Modal, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { api, mensajeError } from '../datos/api';
import { useSesion } from '../estado/Sesion';
import { useZona } from '../estado/Zona';
import { nombreLugar, resumenCriterios, whatsappValido, type Criterios } from '../nucleo';
import { activarNotificaciones } from '../servicios/notificaciones';
import { colores, fuentes } from '../tema';
import { Icono } from './Icono';
import { Ingreso } from './Ingreso';
import { Aviso, Boton, Campo, Casilla, Tarjeta, Texto, Titulo } from './ui';

export function GuardarBusqueda({ visible, onCerrar, texto, criterios }: { visible: boolean; onCerrar: () => void; texto: string; criterios: Criterios }) {
  const insets = useSafeAreaInsets();
  const { usuario } = useSesion();
  const { zona } = useZona();
  const [nombre, setNombre] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [autoriza, setAutoriza] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listo, setListo] = useState<null | { avisos: boolean }>(null);

  // Si escribió un lugar en la búsqueda, ese es su punto de referencia.
  const lugar = criterios.lugar ?? zona;

  const guardar = async () => {
    setError(null);
    if (!nombre.trim()) return setError('Escribí tu nombre.');
    if (!whatsappValido(whatsapp)) return setError('Escribí un WhatsApp válido (ej.: 099 123 456).');
    setGuardando(true);
    try {
      await api.guardarBusqueda({
        texto: texto.trim() || resumenCriterios(criterios),
        criterios,
        nombre: nombre.trim(),
        whatsapp: whatsapp.trim(),
        autoriza_contacto: autoriza,
        departamento: lugar.departamento,
        ciudad: lugar.ciudad,
        lat: lugar.lat,
        lng: lugar.lng,
      });
      const avisos = await activarNotificaciones({ pedirPermiso: true }).catch(() => false);
      setListo({ avisos });
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setGuardando(false);
    }
  };

  const cerrar = () => {
    setListo(null);
    setError(null);
    onCerrar();
  };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={cerrar}>
      <View style={[estilos.modal, { paddingTop: insets.top + 8 }]}>
        <View style={estilos.cabecera}>
          <Titulo nivel={2} style={{ flex: 1 }}>Avisame cuando aparezca</Titulo>
          <Pressable accessibilityRole="button" accessibilityLabel="Cerrar" onPress={cerrar} hitSlop={10}>
            <Icono nombre="x" />
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: insets.bottom + 32 }} keyboardShouldPersistTaps="handled">
          <Tarjeta style={{ marginBottom: 16, backgroundColor: colores.bandaClara, borderColor: colores.bandaClara }}>
            <Text style={estilos.busca}>Buscás</Text>
            <Text style={estilos.resumen}>{resumenCriterios(criterios)}</Text>
            <Text style={estilos.donde}>📍 Medimos la distancia desde {nombreLugar(lugar.departamento, lugar.ciudad)}</Text>
          </Tarjeta>

          {listo ? (
            <View>
              <Aviso tipo="ok">¡Listo! Guardamos tu búsqueda.</Aviso>
              <Texto style={{ marginBottom: 16 }}>
                {api.vistaPrevia
                  ? 'En la vista previa no hay notificaciones reales: en unos segundos vas a ver un aviso de ejemplo acá mismo en la app, y queda en "Alertas".'
                  : listo.avisos
                    ? 'Cuando alguien publique un vehículo que coincida, te llega una notificación al celular diciendo dónde está y a qué distancia.'
                    : Platform.OS === 'web'
                      ? 'Desde la web no podemos mandarte notificaciones: lo que aparezca lo vas a ver en "Alertas". Instalá la app para recibir avisos al celular.'
                      : 'No tenemos permiso para mandarte notificaciones. Lo que aparezca lo vas a ver en "Alertas". Podés activarlas en los ajustes del celular.'}
              </Texto>
              <Boton titulo="Ver mis alertas" icono="campana" onPress={() => { cerrar(); router.push('/alertas'); }} />
              <Boton titulo="Seguir buscando" variante="secundario" onPress={cerrar} style={{ marginTop: 10 }} />
            </View>
          ) : !usuario ? (
            <Ingreso explicacion="Para avisarte necesitamos saber quién sos. Ingresá con tu email, sin contraseña." />
          ) : (
            <View>
              <Campo etiqueta="Tu nombre" value={nombre} onChangeText={setNombre} autoComplete="name" placeholder="Ej.: Lucía" />
              <Campo
                etiqueta="Tu WhatsApp"
                value={whatsapp}
                onChangeText={setWhatsapp}
                keyboardType="phone-pad"
                autoComplete="tel"
                placeholder="099 123 456"
              />
              <Casilla marcada={autoriza} onCambio={setAutoriza}>
                Autorizo que automotoras que tengan lo que busco me contacten por WhatsApp.
              </Casilla>
              <Texto style={estilos.nota}>
                Tu nombre y WhatsApp solo se comparten con automotoras si marcás esta casilla. Podés borrar la búsqueda cuando quieras.
              </Texto>
              {Platform.OS !== 'web' && !api.vistaPrevia ? (
                <Texto style={estilos.nota}>Te vamos a pedir permiso para mandarte notificaciones: es la forma de avisarte cuando aparezca.</Texto>
              ) : null}
              {error ? <Aviso tipo="error">{error}</Aviso> : null}
              <Boton titulo="Avisame" icono="campana" onPress={guardar} cargando={guardando} />
            </View>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  modal: { flex: 1, backgroundColor: colores.fondo },
  cabecera: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 },
  busca: { fontFamily: fuentes.semi, fontSize: 13, color: colores.banda, textTransform: 'uppercase', letterSpacing: 0.5 },
  resumen: { fontFamily: fuentes.titulo, fontSize: 20, color: colores.tinta, marginTop: 2 },
  donde: { fontFamily: fuentes.normal, fontSize: 14, color: colores.gris, marginTop: 6 },
  nota: { fontSize: 14, color: colores.gris, marginVertical: 8 },
});
