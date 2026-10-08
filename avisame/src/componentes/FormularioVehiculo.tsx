// Formulario para publicar o editar un vehículo (particulares y automotoras).
import { useMemo, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { api, mensajeError } from '../datos/api';
import type { Automotora, DatosVehiculo, Vehiculo } from '../datos/tipos';
import {
  CATALOGO,
  COMBUSTIBLES,
  DEPARTAMENTOS,
  MAX_FOTOS,
  TIPOS,
  TRANSMISIONES,
  formatoNumero,
  modelosDe,
  tipoSugerido,
  validarPublicacion,
  type Combustible,
  type Tipo,
  type Transmision,
} from '../nucleo';
import { elegirDeGaleria, sacarFoto } from '../servicios/fotos';
import { colores, fuentes, radio } from '../tema';
import { FotoVehiculo } from './FotoVehiculo';
import { Icono } from './Icono';
import { Selector } from './Selector';
import { Aviso, Boton, Campo, Casilla, Opciones, Texto, Titulo } from './ui';

const soloNumeros = (t: string) => t.replace(/\D/g, '');
const conPuntos = (t: string) => (t ? formatoNumero(Number(t)) : '');

export function FormularioVehiculo({
  inicial, automotora, onGuardado,
}: { inicial?: Vehiculo | null; automotora?: Automotora | null; onGuardado: (id: string) => void }) {
  const [fotos, setFotos] = useState<string[]>(inicial?.fotos ?? []);
  const [marca, setMarca] = useState(inicial?.marca ?? '');
  const [modelo, setModelo] = useState(inicial?.modelo ?? '');
  const [version, setVersion] = useState(inicial?.version ?? '');
  const [anio, setAnio] = useState(inicial ? String(inicial.anio) : '');
  const [km, setKm] = useState(inicial ? String(inicial.km) : '');
  const [precio, setPrecio] = useState(inicial ? String(inicial.precio_usd) : '');
  const [transmision, setTransmision] = useState<Transmision | null>(inicial?.transmision ?? null);
  const [combustible, setCombustible] = useState<Combustible | null>(inicial?.combustible ?? null);
  const [tipo, setTipo] = useState<Tipo | null>(inicial?.tipo ?? null);
  const [x4, setX4] = useState(inicial?.traccion_4x4 ?? false);
  const [descripcion, setDescripcion] = useState(inicial?.descripcion ?? '');
  const [departamento, setDepartamento] = useState(inicial?.departamento ?? automotora?.departamento ?? '');
  const [ciudad, setCiudad] = useState(inicial?.ciudad ?? automotora?.ciudad ?? '');
  const [direccion, setDireccion] = useState(inicial?.direccion ?? (automotora && !inicial ? automotora.direccion ?? '' : ''));
  const [contactoNombre, setContactoNombre] = useState(inicial?.contacto_nombre ?? '');
  const [contactoWhatsapp, setContactoWhatsapp] = useState(inicial?.contacto_whatsapp ?? '');
  const [errores, setErrores] = useState<string[]>([]);
  const [guardando, setGuardando] = useState(false);

  const esAutomotora = !!automotora || !!inicial?.automotora_id;
  const marcas = useMemo(() => CATALOGO.map((m) => m.marca), []);
  const modelos = useMemo(() => modelosDe(marca).map((m) => m.nombre), [marca]);
  const ciudades = useMemo(() => DEPARTAMENTOS.find((d) => d.nombre === departamento)?.ciudades.map((c) => c.nombre) ?? [], [departamento]);

  const agregar = async (desde: 'galeria' | 'camara') => {
    if (desde === 'galeria') {
      const nuevas = await elegirDeGaleria(fotos.length);
      setFotos((f) => [...f, ...nuevas].slice(0, MAX_FOTOS));
    } else {
      const foto = await sacarFoto();
      if (foto) setFotos((f) => [...f, foto].slice(0, MAX_FOTOS));
    }
  };

  const guardar = async () => {
    const datos: DatosVehiculo = {
      marca: marca.trim(), modelo: modelo.trim(), version: version ?? '', anio: Number(anio), km: Number(km || NaN),
      precio_usd: Number(precio), transmision: transmision as Transmision, combustible: combustible as Combustible,
      tipo: tipo as Tipo, traccion_4x4: x4, descripcion: descripcion ?? '', departamento, ciudad, direccion: direccion ?? '',
      contacto_nombre: contactoNombre.trim(), contacto_whatsapp: contactoWhatsapp.trim(),
    };
    const e = validarPublicacion({ ...datos, transmision: transmision ?? '', combustible: combustible ?? '', tipo: tipo ?? '', fotos: fotos.length, esAutomotora });
    setErrores(e);
    if (e.length) return;
    setGuardando(true);
    try {
      const id = await api.guardarVehiculo(datos, fotos, { id: inicial?.id, automotoraId: automotora?.id });
      onGuardado(id);
    } catch (err) {
      setErrores([mensajeError(err)]);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <View>
      <Titulo nivel={2} style={estilos.seccion}>Fotos</Titulo>
      <Texto style={estilos.nota}>De 1 a {MAX_FOTOS} fotos. La primera es la portada: tocá otra para ponerla primera.</Texto>
      <View style={estilos.fotos}>
        {fotos.map((f, i) => (
          <Pressable
            key={f + i}
            accessibilityRole="button"
            accessibilityLabel={i === 0 ? 'Foto de portada' : `Foto ${i + 1}: poner como portada`}
            onPress={() => setFotos((l) => [l[i], ...l.filter((_, j) => j !== i)])}
            style={estilos.miniatura}
          >
            <FotoVehiculo uri={f} style={StyleSheet.absoluteFill} />
            {i === 0 ? <Text style={estilos.portada}>Portada</Text> : null}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Quitar foto ${i + 1}`}
              hitSlop={8}
              onPress={() => setFotos((l) => l.filter((_, j) => j !== i))}
              style={estilos.quitar}
            >
              <Icono nombre="x" tam={14} color={colores.blanco} />
            </Pressable>
          </Pressable>
        ))}
      </View>
      {fotos.length < MAX_FOTOS ? (
        <View style={{ flexDirection: 'row', gap: 10, marginBottom: 8 }}>
          <Boton titulo="Galería" icono="galeria" variante="claro" chico onPress={() => agregar('galeria')} style={{ flex: 1 }} />
          {Platform.OS !== 'web' ? <Boton titulo="Cámara" icono="camara" variante="claro" chico onPress={() => agregar('camara')} style={{ flex: 1 }} /> : null}
        </View>
      ) : null}

      <Titulo nivel={2} style={estilos.seccion}>El vehículo</Titulo>
      <Selector
        etiqueta="Marca"
        valor={marca}
        opciones={marcas}
        conOtro
        onCambio={(m) => {
          if (m !== marca) setModelo('');
          setMarca(m);
        }}
      />
      <Selector
        etiqueta="Modelo"
        valor={modelo}
        opciones={modelos}
        conOtro
        placeholder={marca ? 'Elegir' : 'Primero elegí la marca'}
        onCambio={(m) => {
          setModelo(m);
          const t = tipoSugerido(marca, m);
          if (t && !tipo) setTipo(t);
        }}
      />
      <Campo etiqueta="Versión (opcional)" value={version ?? ''} onChangeText={setVersion} placeholder="Ej.: 1.6 Limited" maxLength={60} />
      <View style={estilos.fila}>
        <Campo etiqueta="Año" value={anio} onChangeText={(t) => setAnio(soloNumeros(t).slice(0, 4))} keyboardType="number-pad" placeholder="2020" style={{ flex: 1 }} />
        <Campo etiqueta="Kilómetros" value={conPuntos(km)} onChangeText={(t) => setKm(soloNumeros(t).slice(0, 7))} keyboardType="number-pad" placeholder="45.000" style={{ flex: 1.3 }} />
      </View>
      <Campo etiqueta="Precio en dólares (USD)" value={conPuntos(precio)} onChangeText={(t) => setPrecio(soloNumeros(t).slice(0, 7))} keyboardType="number-pad" placeholder="18.500" />
      <Opciones etiqueta="Transmisión" opciones={TRANSMISIONES} valor={transmision} onCambio={setTransmision} />
      <Opciones etiqueta="Combustible" opciones={COMBUSTIBLES} valor={combustible} onCambio={setCombustible} />
      <Opciones etiqueta="Tipo" opciones={TIPOS} valor={tipo} onCambio={setTipo} />
      <Casilla marcada={x4} onCambio={setX4}>Es 4x4</Casilla>
      <Campo
        etiqueta="Descripción (opcional)"
        value={descripcion ?? ''}
        onChangeText={setDescripcion}
        multiline
        maxLength={2000}
        placeholder="Estado, service, detalles, si acepta permuta…"
        style={{ marginTop: 8 }}
      />

      <Titulo nivel={2} style={estilos.seccion}>¿Dónde está?</Titulo>
      <Selector
        etiqueta="Departamento"
        valor={departamento}
        opciones={DEPARTAMENTOS.map((d) => d.nombre)}
        onCambio={(d) => {
          setDepartamento(d);
          setCiudad(DEPARTAMENTOS.find((x) => x.nombre === d)?.ciudades[0].nombre ?? '');
        }}
      />
      <Selector etiqueta="Ciudad" valor={ciudad} opciones={ciudades} onCambio={setCiudad} placeholder={departamento ? 'Elegir' : 'Primero elegí el departamento'} />
      <Campo etiqueta="Dirección (opcional)" value={direccion ?? ''} onChangeText={setDireccion} placeholder="Para el botón “Ver en el mapa”" maxLength={120} />

      {esAutomotora ? (
        <Aviso>El nombre y el teléfono de la automotora se completan solos en la publicación.</Aviso>
      ) : (
        <>
          <Titulo nivel={2} style={estilos.seccion}>Contacto</Titulo>
          <Campo etiqueta="Tu nombre" value={contactoNombre} onChangeText={setContactoNombre} autoComplete="name" maxLength={80} />
          <Campo
            etiqueta="WhatsApp"
            value={contactoWhatsapp}
            onChangeText={setContactoWhatsapp}
            keyboardType="phone-pad"
            autoComplete="tel"
            placeholder="099 123 456"
            ayuda="Aparece en la publicación para que te escriban o te llamen."
          />
        </>
      )}

      {errores.length ? (
        <Aviso tipo="error">{errores.join('\n')}</Aviso>
      ) : null}
      <Boton titulo={inicial ? 'Guardar cambios' : 'Publicar'} icono={inicial ? 'check' : 'mas'} onPress={guardar} cargando={guardando} style={{ marginTop: 8 }} />
      {!inicial ? (
        <Texto style={[estilos.nota, { marginTop: 10, textAlign: 'center' }]}>
          Al publicar aceptás los términos de uso. Avisamos al instante a quienes estén buscando un vehículo como el tuyo.
        </Texto>
      ) : null}
    </View>
  );
}

const estilos = StyleSheet.create({
  seccion: { marginTop: 18, marginBottom: 8 },
  nota: { fontSize: 14, color: colores.gris, marginBottom: 10 },
  fotos: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 10 },
  miniatura: { width: 96, height: 72, borderRadius: radio.chico, overflow: 'hidden', backgroundColor: colores.borde },
  portada: {
    position: 'absolute', left: 0, right: 0, bottom: 0, textAlign: 'center', backgroundColor: 'rgba(30,58,138,0.85)',
    color: colores.blanco, fontFamily: fuentes.semi, fontSize: 12, paddingVertical: 2,
  },
  quitar: { position: 'absolute', top: 4, right: 4, width: 22, height: 22, borderRadius: 11, backgroundColor: 'rgba(20,33,61,0.8)', alignItems: 'center', justifyContent: 'center' },
  fila: { flexDirection: 'row', gap: 10 },
});
