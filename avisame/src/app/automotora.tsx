// Panel de automotoras: Clientes, Cargar, Inventario y Plan.
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useCallback, useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { confirmar } from '../componentes/confirmar';
import { FormularioVehiculo } from '../componentes/FormularioVehiculo';
import { Ingreso } from '../componentes/Ingreso';
import { Selector } from '../componentes/Selector';
import { TarjetaVehiculo } from '../componentes/TarjetaVehiculo';
import { Aviso, Boton, Campo, Cargando, Pantalla, Tarjeta, Texto, Titulo } from '../componentes/ui';
import { api, mensajeError } from '../datos/api';
import type { Automotora, Cliente, RegistroPago, Vehiculo } from '../datos/tipos';
import { useSesion } from '../estado/Sesion';
import {
  DEPARTAMENTOS,
  PLANES,
  distanciaA,
  formatoPesos,
  nombreLugar,
  normalizarWhatsapp,
  resumenCriterios,
  textoDistancia,
  type PlanId,
} from '../nucleo';
import { colores, fuentes, radio } from '../tema';

type Pestana = 'clientes' | 'cargar' | 'inventario' | 'plan';
const PESTANAS: { id: Pestana; nombre: string }[] = [
  { id: 'clientes', nombre: 'Clientes' },
  { id: 'cargar', nombre: 'Cargar' },
  { id: 'inventario', nombre: 'Inventario' },
  { id: 'plan', nombre: 'Plan' },
];

const fecha = (iso: string | null) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
};

export default function PanelAutomotora() {
  const { usuario, listo } = useSesion();
  const params = useLocalSearchParams<{ pestana?: string }>();
  const [a, setA] = useState<Automotora | null | undefined>(undefined);
  const [pestana, setPestana] = useState<Pestana>('clientes');
  const [editando, setEditando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (params.pestana && PESTANAS.some((p) => p.id === params.pestana)) setPestana(params.pestana as Pestana);
  }, [params.pestana]);

  const cargar = useCallback(async () => {
    if (!usuario) return;
    try {
      setA(await api.miAutomotora());
    } catch (e) {
      setError(mensajeError(e));
      setA(null);
    }
  }, [usuario]);
  useFocusEffect(useCallback(() => { cargar(); }, [cargar]));

  if (!listo) return <Cargando />;
  if (!usuario) {
    return (
      <Pantalla>
        <Titulo>Automotoras</Titulo>
        <Texto style={{ color: colores.gris, marginVertical: 8 }}>
          Cargá tu inventario, mirá cuántas personas buscan lo que tenés y contactá a los clientes que lo autorizaron.
        </Texto>
        <Tarjeta><Ingreso explicacion="Ingresá con el email de la automotora." /></Tarjeta>
      </Pantalla>
    );
  }
  if (a === undefined) return <Cargando />;
  if (a === null || editando) {
    return (
      <Pantalla>
        <Titulo>{a ? 'Datos de la automotora' : 'Registrá tu automotora'}</Titulo>
        <Texto style={{ color: colores.gris, marginVertical: 8 }}>
          Estos datos se completan solos en cada vehículo que cargues.
        </Texto>
        {error ? <Aviso tipo="error">{error}</Aviso> : null}
        <DatosAutomotora inicial={a} onListo={() => { setEditando(false); cargar(); }} onCancelar={a ? () => setEditando(false) : undefined} />
      </Pantalla>
    );
  }

  const plan = PLANES[a.plan_vigente];
  return (
    <Pantalla>
      <View style={estilos.cabecera}>
        <View style={{ flex: 1 }}>
          <Titulo nivel={2}>{a.nombre}</Titulo>
          <Texto style={{ color: colores.gris }}>📍 {nombreLugar(a.departamento, a.ciudad)} · {a.telefono}</Texto>
        </View>
        {!a.cobros_activos ? (
          <View style={[estilos.plan, { backgroundColor: colores.verdeFondo }]}>
            <Text style={[estilos.planTexto, { color: colores.verde }]}>Lanzamiento · gratis</Text>
          </View>
        ) : (
          <View style={[estilos.plan, a.plan_vigente !== 'gratis' && { backgroundColor: a.plan_vigente === 'destacado' ? colores.doradoFondo : colores.verdeFondo }]}>
            <Text style={[estilos.planTexto, a.plan_vigente === 'destacado' && { color: colores.dorado }, a.plan_vigente === 'pro' && { color: colores.verde }]}>
              {a.plan_vigente === 'destacado' ? '★ ' : ''}{plan.nombre}
            </Text>
          </View>
        )}
      </View>
      <Pressable accessibilityRole="button" onPress={() => setEditando(true)} style={{ alignSelf: 'flex-start', marginBottom: 12 }}>
        <Text style={estilos.enlace}>Editar datos de la automotora</Text>
      </Pressable>

      <View style={estilos.pestanas} accessibilityRole="tablist">
        {PESTANAS.map((p) => (
          <Pressable
            key={p.id}
            accessibilityRole="tab"
            accessibilityState={{ selected: pestana === p.id }}
            onPress={() => setPestana(p.id)}
            style={[estilos.pestana, pestana === p.id && estilos.pestanaActiva]}
          >
            <Text style={[estilos.pestanaTexto, pestana === p.id && { color: colores.blanco }]}>{p.nombre}</Text>
          </Pressable>
        ))}
      </View>

      {pestana === 'clientes' ? <Clientes a={a} irAPlan={() => setPestana('plan')} /> : null}
      {pestana === 'cargar' ? (
        <FormularioVehiculo automotora={a} onGuardado={(id) => router.push(`/vehiculo/${id}`)} />
      ) : null}
      {pestana === 'inventario' ? <Inventario a={a} irACargar={() => setPestana('cargar')} /> : null}
      {pestana === 'plan' ? <Plan a={a} recargar={cargar} /> : null}
    </Pantalla>
  );
}

function DatosAutomotora({ inicial, onListo, onCancelar }: { inicial: Automotora | null; onListo: () => void; onCancelar?: () => void }) {
  const [nombre, setNombre] = useState(inicial?.nombre ?? '');
  const [departamento, setDepartamento] = useState(inicial?.departamento ?? '');
  const [ciudad, setCiudad] = useState(inicial?.ciudad ?? '');
  const [direccion, setDireccion] = useState(inicial?.direccion ?? '');
  const [telefono, setTelefono] = useState(inicial?.telefono ?? '');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ciudades = DEPARTAMENTOS.find((d) => d.nombre === departamento)?.ciudades.map((c) => c.nombre) ?? [];

  const guardar = async () => {
    setError(null);
    if (nombre.trim().length < 2) return setError('Escribí el nombre de la automotora.');
    if (!departamento || !ciudad) return setError('Elegí departamento y ciudad.');
    if (!normalizarWhatsapp(telefono)) return setError('Escribí un teléfono o WhatsApp válido.');
    setGuardando(true);
    try {
      await api.guardarAutomotora({ nombre: nombre.trim(), departamento, ciudad, direccion, telefono: telefono.trim() });
      onListo();
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <View>
      <Campo etiqueta="Nombre de la automotora" value={nombre} onChangeText={setNombre} maxLength={80} />
      <Selector
        etiqueta="Departamento"
        valor={departamento}
        opciones={DEPARTAMENTOS.map((d) => d.nombre)}
        onCambio={(d) => { setDepartamento(d); setCiudad(DEPARTAMENTOS.find((x) => x.nombre === d)?.ciudades[0].nombre ?? ''); }}
      />
      <Selector etiqueta="Ciudad" valor={ciudad} opciones={ciudades} onCambio={setCiudad} />
      <Campo etiqueta="Dirección" value={direccion} onChangeText={setDireccion} maxLength={120} placeholder="Ej.: Av. Italia 1234" />
      <Campo etiqueta="Teléfono o WhatsApp" value={telefono} onChangeText={setTelefono} keyboardType="phone-pad" placeholder="099 123 456" />
      {error ? <Aviso tipo="error">{error}</Aviso> : null}
      <Boton titulo="Guardar" icono="check" onPress={guardar} cargando={guardando} />
      {onCancelar ? <Boton titulo="Cancelar" variante="secundario" onPress={onCancelar} style={{ marginTop: 10 }} /> : null}
    </View>
  );
}

function Clientes({ a, irAPlan }: { a: Automotora; irAPlan: () => void }) {
  const [lista, setLista] = useState<Cliente[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [contactos, setContactos] = useState<Record<string, { nombre: string; whatsapp: string } | { error: string }>>({});
  // En el modo lanzamiento todas las automotoras ven los contactos autorizados.
  const verContactos = !a.cobros_activos || PLANES[a.plan_vigente].verContactos;

  useEffect(() => {
    api.clientes().then(setLista).catch((e) => setError(mensajeError(e)));
  }, []);

  const pedirContacto = async (id: string) => {
    try {
      const c = await api.contactoCliente(id);
      setContactos((x) => ({ ...x, [id]: c }));
    } catch (e) {
      setContactos((x) => ({ ...x, [id]: { error: mensajeError(e) } }));
    }
  };

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!lista) return <Cargando />;
  return (
    <View>
      <Tarjeta style={{ marginBottom: 14, backgroundColor: colores.bandaClara, borderColor: colores.bandaClara }}>
        <Text style={estilos.numero}>{lista.length}</Text>
        <Texto style={{ color: colores.banda, fontFamily: fuentes.semi }}>
          {lista.length === 1 ? 'persona busca' : 'personas buscan'} algo que tenés en tu inventario
        </Texto>
      </Tarjeta>
      {!verContactos ? (
        <Tarjeta style={{ marginBottom: 14 }}>
          <Texto>Con el plan <Texto style={{ fontFamily: fuentes.negrita }}>Pro</Texto> ves el contacto de los clientes que lo autorizaron y te avisamos al celular cuando aparece uno nuevo.</Texto>
          <Boton titulo="Ver planes" chico variante="claro" onPress={irAPlan} style={{ marginTop: 10, alignSelf: 'flex-start' }} />
        </Tarjeta>
      ) : null}
      {lista.length === 0 ? (
        <Texto style={{ color: colores.gris }}>
          Todavía nadie guardó una búsqueda que coincida con tu inventario. Cuando pase, aparece acá{verContactos ? ' y te avisamos al celular' : ''}.
        </Texto>
      ) : (
        lista.map((c) => {
          const contacto = contactos[c.busqueda_id];
          const wa = contacto && 'whatsapp' in contacto ? normalizarWhatsapp(contacto.whatsapp) : null;
          return (
            <Tarjeta key={c.busqueda_id} style={{ marginBottom: 12 }}>
              <Text style={estilos.clienteBusca}>Busca</Text>
              <Text style={estilos.clienteTitulo}>{resumenCriterios(c.criterios)}</Text>
              <Texto style={{ marginTop: 4 }}>
                📍 Está en {nombreLugar(c.departamento, c.ciudad)} · {textoDistancia(distanciaA(c, a))} de tu automotora
              </Texto>
              <Texto style={{ color: colores.gris, fontSize: 14, marginTop: 4 }}>
                Coincide con: {c.vehiculos.map((v) => `${v.marca} ${v.modelo} ${v.anio}`).join(', ')}
              </Texto>
              {!c.autoriza_contacto ? (
                <Texto style={{ color: colores.gris, fontSize: 14, marginTop: 8 }}>🔒 No autorizó que lo contacten.</Texto>
              ) : !verContactos ? (
                <Texto style={{ color: colores.gris, fontSize: 14, marginTop: 8 }}>🔒 Autorizó el contacto. Lo ves con el plan Pro o Destacado.</Texto>
              ) : contacto && 'nombre' in contacto ? (
                <View style={{ marginTop: 10 }}>
                  <Text style={estilos.clienteNombre}>{contacto.nombre} · {contacto.whatsapp}</Text>
                  {wa ? (
                    <Boton
                      titulo="Escribir por WhatsApp"
                      icono="whatsapp"
                      variante="whatsapp"
                      chico
                      onPress={() => Linking.openURL(`https://wa.me/${wa}?text=${encodeURIComponent(`Hola ${contacto.nombre}, te escribimos de ${a.nombre}. Vimos en Avisame que buscás ${resumenCriterios(c.criterios)}.`)}`)}
                      style={{ marginTop: 8, alignSelf: 'flex-start' }}
                    />
                  ) : null}
                </View>
              ) : contacto && 'error' in contacto ? (
                <Aviso tipo="error">{contacto.error}</Aviso>
              ) : (
                <Boton titulo="Ver contacto" icono="persona" chico variante="claro" onPress={() => pedirContacto(c.busqueda_id)} style={{ marginTop: 10, alignSelf: 'flex-start' }} />
              )}
            </Tarjeta>
          );
        })
      )}
    </View>
  );
}

function Inventario({ a, irACargar }: { a: Automotora; irACargar: () => void }) {
  const [lista, setLista] = useState<Vehiculo[] | null>(null);
  useFocusEffect(
    useCallback(() => {
      api.misVehiculos().then((l) => setLista(l.filter((v) => v.automotora_id === a.id))).catch(() => setLista([]));
    }, [a.id]),
  );
  if (!lista) return <Cargando />;
  if (lista.length === 0) {
    return (
      <View>
        <Texto style={{ color: colores.gris, marginBottom: 12 }}>Todavía no cargaste vehículos.</Texto>
        <Boton titulo="Cargar un vehículo" icono="mas" onPress={irACargar} />
      </View>
    );
  }
  return (
    <View>
      <Texto style={{ color: colores.gris, marginBottom: 10 }}>
        {lista.filter((v) => v.estado === 'activo').length} publicados · tocá uno para editarlo, pausarlo o marcarlo vendido.
      </Texto>
      {lista.map((v) => <TarjetaVehiculo key={v.id} v={v} estado />)}
    </View>
  );
}

function Plan({ a, recargar }: { a: Automotora; recargar: () => Promise<void> }) {
  const [pagos, setPagos] = useState<RegistroPago[]>([]);
  const [trabajando, setTrabajando] = useState<PlanId | 'cancelar' | null>(null);
  const [mensaje, setMensaje] = useState<{ tipo: 'ok' | 'error' | 'info'; texto: string } | null>(null);

  useEffect(() => {
    api.pagos().then(setPagos).catch(() => {});
  }, [a.plan_vence]);

  const suscribirse = async (plan: 'pro' | 'destacado') => {
    setTrabajando(plan);
    setMensaje(null);
    try {
      const url = await api.suscribirse(plan);
      if (api.vistaPrevia) {
        setMensaje({ tipo: 'info', texto: 'Vista previa: se simuló el cobro. En la app real se abre Mercado Pago y el plan se activa recién cuando Mercado Pago confirma el pago.' });
      } else {
        await WebBrowser.openBrowserAsync(url);
        setMensaje({ tipo: 'info', texto: 'Cuando Mercado Pago confirme el pago, tu plan se activa solo. Puede demorar unos minutos.' });
      }
      await recargar();
    } catch (e) {
      setMensaje({ tipo: 'error', texto: mensajeError(e) });
    } finally {
      setTrabajando(null);
    }
  };

  const cancelar = () =>
    confirmar('Cancelar la renovación', `Tu plan sigue activo hasta el ${fecha(a.plan_vence)} y después pasa a Gratis. No se te cobra más.`, 'Cancelar renovación', async () => {
      setTrabajando('cancelar');
      try {
        await api.cancelarSuscripcion();
        await recargar();
        setMensaje({ tipo: 'ok', texto: `Listo. No se renueva más; el plan sigue hasta el ${fecha(a.plan_vence)}.` });
      } catch (e) {
        setMensaje({ tipo: 'error', texto: mensajeError(e) });
      } finally {
        setTrabajando(null);
      }
    });

  if (!a.cobros_activos) {
    return (
      <Tarjeta>
        <Text style={estilos.clienteBusca}>Lanzamiento</Text>
        <Text style={estilos.clienteTitulo}>Avisame es gratis para automotoras</Text>
        <Texto style={{ marginTop: 6 }}>Mientras dure el lanzamiento tenés todo sin costo:</Texto>
        <Texto style={{ marginTop: 6 }}>✓ Publicar todo tu inventario</Texto>
        <Texto style={{ marginTop: 4 }}>✓ Ver cuántas personas buscan lo que tenés</Texto>
        <Texto style={{ marginTop: 4 }}>✓ El contacto de los clientes que lo autorizaron</Texto>
        <Texto style={{ marginTop: 4 }}>✓ Aviso al celular cuando aparece un cliente nuevo</Texto>
        <Texto style={{ color: colores.gris, fontSize: 14, marginTop: 12 }}>
          Más adelante habrá planes pagos. Te vamos a avisar con anticipación y nunca se cobra nada sin que te suscribas.
        </Texto>
      </Tarjeta>
    );
  }

  const activo = a.plan_vigente !== 'gratis';
  const renueva = activo && a.tiene_suscripcion && !a.renovacion_cancelada;
  const esperando = !activo && a.mp_estado === 'pending';

  return (
    <View>
      <Tarjeta style={{ marginBottom: 14 }}>
        <Text style={estilos.clienteBusca}>Tu plan</Text>
        <Text style={estilos.clienteTitulo}>{PLANES[a.plan_vigente].nombre}</Text>
        {activo ? (
          <Texto style={{ marginTop: 4 }}>
            {renueva ? `Se renueva solo el ${fecha(a.plan_vence)}.` : `Activo hasta el ${fecha(a.plan_vence)}. No se renueva.`}
          </Texto>
        ) : esperando ? (
          <Texto style={{ marginTop: 4 }}>Esperando la confirmación del pago de Mercado Pago.</Texto>
        ) : null}
        {renueva ? (
          <Boton titulo="Cancelar renovación" variante="peligro" chico cargando={trabajando === 'cancelar'} onPress={cancelar} style={{ marginTop: 12, alignSelf: 'flex-start' }} />
        ) : null}
        {esperando ? <Boton titulo="Actualizar" variante="claro" chico onPress={recargar} style={{ marginTop: 12, alignSelf: 'flex-start' }} /> : null}
      </Tarjeta>
      {mensaje ? <Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso> : null}

      {(Object.keys(PLANES) as PlanId[]).map((id) => {
        const p = PLANES[id];
        const actual = a.plan_vigente === id;
        return (
          <Tarjeta key={id} style={[{ marginBottom: 12 }, actual && { borderColor: colores.banda, borderWidth: 2 }]}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}>
              <Text style={estilos.planNombre}>{p.destacado ? '★ ' : ''}{p.nombre}</Text>
              <Text style={estilos.planPrecio}>{p.precioUYU ? `${formatoPesos(p.precioUYU)}/mes` : 'Gratis'}</Text>
            </View>
            {p.beneficios.map((b) => <Texto key={b} style={{ marginTop: 4 }}>✓ {b}</Texto>)}
            {id !== 'gratis' && !actual && !renueva ? (
              <Boton
                titulo={`Suscribirme a ${p.nombre}`}
                onPress={() => suscribirse(id as 'pro' | 'destacado')}
                cargando={trabajando === id}
                style={{ marginTop: 12 }}
              />
            ) : actual ? (
              <Text style={[estilos.enlace, { marginTop: 10, textDecorationLine: 'none' }]}>Tu plan actual</Text>
            ) : null}
          </Tarjeta>
        );
      })}
      <Texto style={{ color: colores.gris, fontSize: 14 }}>
        Precios en pesos uruguayos. Cobro mensual con Mercado Pago. Podés cancelar la renovación cuando quieras: el plan sigue hasta el final del período pagado.
      </Texto>

      <Titulo nivel={3} style={{ marginTop: 20, marginBottom: 8 }}>Historial de pagos</Titulo>
      {pagos.length === 0 ? (
        <Texto style={{ color: colores.gris }}>Todavía no hay pagos.</Texto>
      ) : (
        pagos.map((p) => (
          <View key={p.id} style={estilos.pago}>
            <View style={{ flex: 1 }}>
              <Text style={estilos.pagoTitulo}>Plan {PLANES[p.plan].nombre} · {formatoPesos(p.monto)}</Text>
              <Text style={estilos.pagoDetalle}>{fecha(p.creado)} · cubre hasta el {fecha(p.periodo_hasta)}</Text>
            </View>
            <Text style={estilos.pagoEstado}>{p.estado.startsWith('approved') ? 'Aprobado' : p.estado}</Text>
          </View>
        ))
      )}
    </View>
  );
}

const estilos = StyleSheet.create({
  cabecera: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 4 },
  plan: { backgroundColor: colores.bandaClara, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  planTexto: { fontFamily: fuentes.negrita, fontSize: 14, color: colores.banda },
  enlace: { fontFamily: fuentes.semi, fontSize: 15, color: colores.banda, textDecorationLine: 'underline' },
  pestanas: { flexDirection: 'row', backgroundColor: colores.blanco, borderRadius: radio.medio, padding: 4, marginBottom: 16, borderWidth: 1, borderColor: colores.borde },
  pestana: { flex: 1, minHeight: 42, alignItems: 'center', justifyContent: 'center', borderRadius: radio.chico },
  pestanaActiva: { backgroundColor: colores.banda },
  pestanaTexto: { fontFamily: fuentes.semi, fontSize: 15, color: colores.tinta },
  numero: { fontFamily: fuentes.titulo, fontSize: 40, color: colores.banda, lineHeight: 44 },
  clienteBusca: { fontFamily: fuentes.semi, fontSize: 13, color: colores.gris, textTransform: 'uppercase', letterSpacing: 0.5 },
  clienteTitulo: { fontFamily: fuentes.titulo, fontSize: 20, color: colores.tinta },
  clienteNombre: { fontFamily: fuentes.semi, fontSize: 17, color: colores.tinta },
  planNombre: { fontFamily: fuentes.titulo, fontSize: 22, color: colores.tinta },
  planPrecio: { fontFamily: fuentes.semi, fontSize: 17, color: colores.banda },
  pago: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colores.borde },
  pagoTitulo: { fontFamily: fuentes.semi, fontSize: 16, color: colores.tinta },
  pagoDetalle: { fontFamily: fuentes.normal, fontSize: 14, color: colores.gris },
  pagoEstado: { fontFamily: fuentes.semi, fontSize: 14, color: colores.verde },
});
