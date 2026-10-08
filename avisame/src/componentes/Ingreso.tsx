// Ingreso sin contraseña: email → código de 6 dígitos.
import { useState } from 'react';
import { View } from 'react-native';
import { api, mensajeError } from '../datos/api';
import { CODIGO_VISTA_PREVIA } from '../datos/apiDemo';
import { colores } from '../tema';
import { Aviso, Boton, Campo, Texto } from './ui';

export function Ingreso({ onListo, explicacion }: { onListo?: () => void; explicacion?: string }) {
  const [email, setEmail] = useState('');
  const [codigo, setCodigo] = useState('');
  const [paso, setPaso] = useState<'email' | 'codigo'>('email');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pedir = async () => {
    setError(null);
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError('Escribí un email válido.');
    setCargando(true);
    try {
      await api.pedirCodigo(email);
      setPaso('codigo');
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setCargando(false);
    }
  };

  const verificar = async () => {
    setError(null);
    if (!/^\d{6}$/.test(codigo.trim())) return setError('El código tiene 6 números.');
    setCargando(true);
    try {
      await api.verificarCodigo(email, codigo);
      onListo?.();
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setCargando(false);
    }
  };

  return (
    <View>
      {explicacion ? <Texto style={{ color: colores.gris, marginBottom: 14 }}>{explicacion}</Texto> : null}
      {paso === 'email' ? (
        <>
          <Campo
            etiqueta="Tu email"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            textContentType="emailAddress"
            placeholder="nombre@ejemplo.com"
            onSubmitEditing={pedir}
            ayuda="Te mandamos un código de 6 números. No hace falta contraseña."
          />
          {error ? <Aviso tipo="error">{error}</Aviso> : null}
          <Boton titulo="Mandarme el código" onPress={pedir} cargando={cargando} />
        </>
      ) : (
        <>
          <Texto style={{ marginBottom: 12 }}>
            Te mandamos un código a <Texto style={{ fontWeight: '700' }}>{email.trim()}</Texto>. Si no lo ves, mirá en correo no deseado.
          </Texto>
          {api.vistaPrevia ? <Aviso>Vista previa: el código es {CODIGO_VISTA_PREVIA}.</Aviso> : null}
          <Campo
            etiqueta="Código"
            value={codigo}
            onChangeText={(t) => setCodigo(t.replace(/\D/g, '').slice(0, 6))}
            keyboardType="number-pad"
            autoComplete="one-time-code"
            textContentType="oneTimeCode"
            placeholder="123456"
            maxLength={6}
            onSubmitEditing={verificar}
            autoFocus
          />
          {error ? <Aviso tipo="error">{error}</Aviso> : null}
          <Boton titulo="Entrar" onPress={verificar} cargando={cargando} />
          <Boton titulo="Usar otro email" variante="secundario" onPress={() => { setPaso('email'); setCodigo(''); setError(null); }} style={{ marginTop: 10 }} />
        </>
      )}
    </View>
  );
}
