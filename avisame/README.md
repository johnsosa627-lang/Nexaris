# Avisame

Buscador de vehículos de Uruguay. La persona escribe lo que busca como lo diría
(“Busco una Hyundai Creta 2022 o más nueva, menos de 70.000 km y hasta 18.000
dólares”), la app lo entiende, muestra lo que coincide y lo que *casi* coincide,
y si no está, **avisa al celular cuando aparece**.

Una sola base de código para Android (Play Store), iPhone y web: **Expo (React
Native + Expo Router + TypeScript)** y **Supabase** (Postgres con RLS, ingreso con
código por email, fotos y Edge Functions). Cobros a automotoras con **Mercado
Pago** (suscripción mensual).

---

## Índice

1. [Estructura](#1-estructura)
2. [Probarlo en tu computadora (vista previa)](#2-probarlo-en-tu-computadora-vista-previa)
3. [Verificación](#3-verificación)
4. [Crear el proyecto de Supabase](#4-crear-el-proyecto-de-supabase)
5. [Ingreso por email con código de 6 dígitos](#5-ingreso-por-email-con-código-de-6-dígitos)
6. [Publicar las funciones del servidor](#6-publicar-las-funciones-del-servidor)
7. [Mercado Pago: claves y webhook](#7-mercado-pago-claves-y-webhook)
8. [Publicar la web](#8-publicar-la-web)
9. [Compilar la app con EAS](#9-compilar-la-app-con-eas)
10. [Notificaciones con Firebase](#10-notificaciones-con-firebase)
11. [Subir a Google Play](#11-subir-a-google-play)
12. [Fuentes de vehículos](#12-fuentes-de-vehículos)
13. [Cómo está resuelta la seguridad](#13-cómo-está-resuelta-la-seguridad)
14. [Antes de lanzar](#14-antes-de-lanzar)

---

## 1. Estructura

```
avisame/
├── src/
│   ├── app/                     Pantallas (Expo Router)
│   │   ├── (tabs)/              Buscar · Alertas · Publicar · Cuenta
│   │   ├── vehiculo/[id].tsx    Ficha: galería, mapa, WhatsApp, llamar, denunciar
│   │   ├── automotora.tsx       Panel: Clientes · Cargar · Inventario · Plan
│   │   ├── privacidad.tsx       Política de privacidad (Ley 18.331)
│   │   └── terminos.tsx         Términos de uso
│   ├── componentes/             Barra-matrícula, ilustración, tarjetas, formularios…
│   ├── datos/                   api.ts (contrato) · apiSupabase.ts (real) · apiDemo.ts (vista previa)
│   ├── estado/                  Sesión y zona
│   └── servicios/               Fotos, ubicación y notificaciones
├── supabase/
│   ├── migrations/              ← La migración SQL completa
│   └── functions/
│       ├── _shared/nucleo.ts    ← NÚCLEO compartido app + servidor (sin dependencias)
│       ├── _shared/servidor.ts  Utilidades de servidor (push, Mercado Pago, firma)
│       ├── _shared/fuentes.ts   Conversión de fuentes externas (Mercado Libre oficial)
│       ├── match/               Cruza vehículos con búsquedas y avisa (sin repetir)
│       ├── mp-subscribe/        Crea la suscripción (preapproval)
│       ├── mp-webhook/          Único lugar donde se activa un plan
│       ├── mp-cancel/           Cancela la renovación
│       └── delete-account/      Borra la cuenta y cancela la suscripción
├── pruebas/                     Pruebas del núcleo, de la base y de la firma
└── scripts/probar-db.sh         Prueba la migración y los permisos en un Postgres local
```

**El núcleo** (`supabase/functions/_shared/nucleo.ts`) tiene el intérprete de
búsquedas, las reglas de coincidencia (“Coincide” / “Casi” con su motivo), las
distancias, los 19 departamentos con sus ciudades y coordenadas, el catálogo de
marcas y modelos y **los planes con sus precios** (único lugar donde se editan).
La app lo importa desde `src/nucleo.ts` y las funciones desde `../_shared/nucleo.ts`.

El intérprete funciona con reglas locales y devuelve un objeto `Criterios`. Si más
adelante querés que lo genere una IA, alcanza con reemplazar `interpretar()` por
una llamada que devuelva ese mismo objeto: el resto no cambia.

---

## 2. Probarlo en tu computadora (vista previa)

Necesitás Node 20 o más nuevo.

```bash
cd avisame
npm install
npm run web          # abre http://localhost:8081
```

Si no hay credenciales de Supabase, la app arranca sola en **modo vista previa**:
una banda arriba dice “VISTA PREVIA · vehículos y datos de ejemplo”, los
vehículos son de ejemplo, el código para ingresar es **123456**, los avisos al
celular se muestran como un cartel dentro de la app y el cobro se simula. Nada
sale de tu computadora.

En el celular: instalá **Expo Go** y corré `npx expo start`. Para notificaciones
reales hace falta una compilación propia (sección 9), no Expo Go.

---

## 3. Verificación

```bash
npm run typecheck      # TypeScript sin errores
npm run test:nucleo    # Intérprete, coincidencias, distancias, planes (node --test)
npm run build:web      # Compilación web → dist/
npm run test:db        # Migración + 48 comprobaciones de RLS y permisos (necesita Postgres)
```

`test:db` crea una base temporal en un Postgres local, simula lo mínimo de
Supabase (roles `anon`/`authenticated`, `auth.uid()`, `storage`), aplica la
migración y prueba, entre otras cosas, que nadie pueda cambiarse el plan, que el
contacto de un cliente solo salga con plan pago al día **y** consentimiento, que
cada uno suba fotos solo a su carpeta y que borrar la cuenta borre todo. Por
defecto usa `postgresql://postgres:postgres@localhost:5432/postgres`; cambialo con
`DB_URL=... npm run test:db`.

Las funciones del servidor se verifican con Deno:

```bash
cd supabase/functions && deno check */index.ts && cd ../..
deno test pruebas/firma.test.ts     # firma x-signature de Mercado Pago
```

---

## 4. Crear el proyecto de Supabase

1. Entrá a <https://supabase.com>, creá una cuenta y un proyecto nuevo. Región
   recomendada: **South America (São Paulo)**, la más cercana a Uruguay. Guardá la
   contraseña de la base.
2. Aplicá la migración. Con la CLI (recomendado):
   ```bash
   npx supabase login
   npx supabase link --project-ref TU_REF      # el REF está en la URL del proyecto
   npx supabase db push                         # aplica supabase/migrations/
   ```
   O sin CLI: abrí **SQL Editor**, pegá el contenido de
   `supabase/migrations/20261008000000_avisame.sql` y ejecutalo.
3. En **Project Settings → API** copiá la **Project URL** y la clave **anon /
   publishable**. Creá `.env.local` a partir de `.env.example`:
   ```bash
   cp .env.example .env.local
   # EXPO_PUBLIC_SUPABASE_URL=...  EXPO_PUBLIC_SUPABASE_ANON_KEY=...
   ```
   La clave *anon* puede estar en la app: la seguridad la dan las reglas RLS. La
   clave **service_role** nunca va en la app (solo la usan las funciones).
4. **Storage**: la migración crea el bucket público `fotos` (5 MB por archivo,
   JPG/PNG/WebP). Cada usuario solo puede escribir en `fotos/<su id>/`.
5. En **Authentication → URL Configuration** poné como *Site URL* la dirección de
   tu web (sección 8) y agregá `avisame://` en *Redirect URLs*.

---

## 5. Ingreso por email con código de 6 dígitos

No hay contraseñas: la persona escribe su email y recibe un código.

1. **Authentication → Sign In / Providers → Email**: dejalo activado. En *Email OTP
   Length* poné **6** y en *Email OTP Expiration* 900 segundos.
2. **Authentication → Emails → Templates**: en **Magic Link** y en **Confirm
   signup** reemplazá el contenido para que muestre el código (`{{ .Token }}`) en
   vez del enlace. Ejemplo:
   - Asunto: `Tu código de Avisame: {{ .Token }}`
   - Cuerpo:
     ```html
     <h2>Tu código para entrar a Avisame</h2>
     <p style="font-size:32px;letter-spacing:6px"><b>{{ .Token }}</b></p>
     <p>Vence en 15 minutos. Si no lo pediste, ignorá este correo.</p>
     ```
3. **SMTP propio (obligatorio para producción)**: el servidor de correo de prueba
   de Supabase manda muy pocos correos por hora. En **Authentication → Emails →
   SMTP Settings** configurá un proveedor (Resend, Brevo, Amazon SES, etc.) con un
   remitente de tu dominio, por ejemplo `no-responder@avisame.uy`.

---

## 6. Publicar las funciones del servidor

1. Copiá `supabase/.env.example` a `supabase/.env` y completalo (la sección 7
   explica de dónde sale cada valor de Mercado Pago):
   ```
   MP_ACCESS_TOKEN=APP_USR-...
   MP_WEBHOOK_SECRET=...
   APP_URL=https://avisame.uy
   ```
2. Cargá los secretos y publicá:
   ```bash
   npx supabase secrets set --env-file supabase/.env
   npx supabase functions deploy match mp-subscribe mp-cancel delete-account
   npx supabase functions deploy mp-webhook --no-verify-jwt
   ```
   `mp-webhook` va **sin verificación de JWT** porque Mercado Pago no manda el
   token de Supabase: su seguridad es la firma `x-signature` (ya está así en
   `supabase/config.toml`). Las demás exigen una sesión válida.

Qué hace cada una:

| Función | Cuándo se llama | Qué hace |
|---|---|---|
| `match` | Al publicar/editar un vehículo y al guardar una búsqueda | Cruza con el núcleo, guarda cada par búsqueda–vehículo **una sola vez** (`coincidencias`) y manda la notificación con lugar y distancia. Avisa a la automotora cuando aparece un cliente nuevo (una vez por cliente, solo con plan Pro o Destacado). |
| `mp-subscribe` | Automotora toca “Suscribirme” | Crea el *preapproval* mensual en pesos y devuelve el link de pago. **No activa nada.** |
| `mp-webhook` | Mercado Pago avisa | Verifica la firma, vuelve a consultar el pago en la API y, si está **aprobado** y el monto coincide con el plan, registra el pago y extiende el plan un mes. Idempotente. |
| `mp-cancel` | “Cancelar renovación” | Cancela el *preapproval*. El plan sigue hasta `plan_vence`. |
| `delete-account` | “Borrar mi cuenta” | Cancela la suscripción, borra las fotos y el usuario (todo lo demás se borra en cascada). |

---

## 7. Mercado Pago: claves y webhook

> **Modo lanzamiento (así arranca la base).** Mientras no actives los cobros,
> Avisame es gratis para automotoras: todas tienen lo del plan Pro (contactos de
> los clientes que lo autorizaron y avisos al celular), el panel muestra
> “Lanzamiento · gratis” y nadie puede suscribirse. No hace falta configurar
> Mercado Pago todavía. Cuando decidas cobrar (con Mercado Pago ya configurado y
> tu inscripción en DGI/BPS hecha), corré en el **SQL Editor** de Supabase:
> ```sql
> update public.ajustes set cobros_activos = true;
> ```
> Desde ese momento rigen los planes y los precios de `PLANES`. Avisá a las
> automotoras con anticipación (los términos de uso lo prometen).

1. Entrá a <https://www.mercadopago.com.uy/developers> con la cuenta que va a
   **cobrar** y andá a **Tus integraciones → Crear aplicación**. Elegí el producto
   **Suscripciones**.
2. **Credenciales**: en *Credenciales de producción* copiá el **Access Token**
   (`APP_USR-...`) → `MP_ACCESS_TOKEN`. Para probar, usá las *credenciales de
   prueba* y **cuentas de prueba** (Tus integraciones → Cuentas de prueba): una
   vendedora y una compradora. La automotora de prueba tiene que ingresar a
   Avisame con el email de la cuenta compradora, porque ese email se manda como
   `payer_email`.
3. **Webhook**: en tu aplicación → **Webhooks → Configurar notificaciones**:
   - URL de producción: `https://TU_REF.supabase.co/functions/v1/mp-webhook`
   - Eventos: **Planes y suscripciones** (`subscription_preapproval` y
     `subscription_authorized_payment`) y **Pagos** (`payment`).
   - Guardá y copiá la **clave secreta** que muestra → `MP_WEBHOOK_SECRET`.
   - Con “Simular notificación” podés comprobar que responde 200 (si la firma no
     coincide responde 401).
4. Volvé a cargar los secretos (`npx supabase secrets set --env-file supabase/.env`).

**Cómo funciona el cobro**: la automotora elige Pro o Destacado → se abre Mercado
Pago → paga → Mercado Pago avisa al webhook → recién ahí el plan queda activo
hasta un mes después. Cada mes Mercado Pago cobra solo y el webhook extiende el
plan. Si cancela la renovación, no se le cobra más y el plan dura hasta el final
del período pagado. La app **nunca** puede cambiar el plan: la base no le da
permiso sobre esas columnas.

**Cambiar precios o planes**: editá `PLANES` en
`supabase/functions/_shared/nucleo.ts`, volvé a publicar las funciones y la
app/web. Las suscripciones ya creadas mantienen su monto en Mercado Pago.

---

## 8. Publicar la web

```bash
npm run build:web       # genera dist/ (aplicación de una sola página)
```

Las variables `EXPO_PUBLIC_*` se incluyen al compilar, así que definilas antes
(en `.env.local` o en el panel del hosting). Subí `dist/` a cualquier hosting
estático. Como es una SPA, todas las rutas tienen que devolver `index.html`:

- **Netlify**: creá `dist/_redirects` con `/*  /index.html  200` (o configuralo en
  el panel). Comando de build `npm run build:web`, carpeta `dist`.
- **Vercel**: framework “Other”, build `npm run build:web`, output `dist`, y una
  *rewrite* de `/(.*)` a `/index.html`.
- **Cloudflare Pages**: build `npm run build:web`, output `dist` (las SPA ya
  vuelven a `index.html`).

Después poné esa dirección en `APP_URL` (secreto de las funciones) y en la *Site
URL* de Supabase. La política de privacidad queda en `https://tu-dominio/privacidad`
y los términos en `/terminos`: esas son las URL que pide Google Play.

---

## 9. Compilar la app con EAS

1. Creá una cuenta en <https://expo.dev> y ejecutá:
   ```bash
   npx eas-cli@latest login
   npx eas-cli@latest init          # completa extra.eas.projectId en app.json
   ```
2. Cargá las variables para las compilaciones (una por cada valor):
   ```bash
   npx eas-cli env:create --environment production --name EXPO_PUBLIC_SUPABASE_URL --value https://TU_REF.supabase.co --visibility plaintext
   npx eas-cli env:create --environment production --name EXPO_PUBLIC_SUPABASE_ANON_KEY --value TU_CLAVE --visibility plaintext
   npx eas-cli env:create --environment production --name EXPO_PUBLIC_RESPONSABLE --value "Tu nombre o empresa" --visibility plaintext
   npx eas-cli env:create --environment production --name EXPO_PUBLIC_EMAIL_CONTACTO --value contacto@avisame.uy --visibility plaintext
   npx eas-cli env:create --environment production --name EXPO_PUBLIC_DOMICILIO --value "Calle 1234, Montevideo" --visibility plaintext
   ```
   Repetí para `preview` si vas a compilar APKs de prueba.
3. Compilá:
   ```bash
   npx eas-cli build -p android --profile preview      # APK para instalar y probar
   npx eas-cli build -p android --profile production   # AAB para Google Play
   ```
   El identificador de la app es `uy.avisame.app` (en `app.json`). **No se puede
   cambiar después de publicar**: si querés otro, cambialo ahora.

---

## 10. Notificaciones con Firebase

Android entrega las notificaciones a través de Firebase Cloud Messaging (FCM).

1. En <https://console.firebase.google.com> creá un proyecto y agregá una **app
   Android** con el paquete `uy.avisame.app`.
2. Descargá **google-services.json**, ponelo en la carpeta `avisame/` y agregá en
   `app.json`, dentro de `"android"`: `"googleServicesFile": "./google-services.json"`.
3. En Firebase → **Configuración del proyecto → Cuentas de servicio → Generar nueva
   clave privada**. Se descarga un JSON.
4. Subilo a EAS: `npx eas-cli credentials` → Android → production → **Google
   Service Account** → *Manage your Google Service Account Key for Push
   Notifications (FCM V1)* → subí el JSON.
5. Volvé a compilar. Para probar: instalá la app, guardá una búsqueda (acepta el
   permiso) y publicá desde otra cuenta un vehículo que coincida.

(Opcional) Si en expo.dev activás *Enhanced security for push notifications*,
cargá el token de acceso como secreto `EXPO_ACCESS_TOKEN`.

---

## 11. Subir a Google Play

1. **Cuenta de desarrollador**: <https://play.google.com/console> (pago único de
   USD 25 y verificación de identidad).
2. **Requisito para cuentas personales nuevas**: si tu cuenta de desarrollador es
   **personal** y se creó después del 13 de noviembre de 2023, antes de publicar
   en producción tenés que hacer una **prueba cerrada con al menos 12 testers que
   la tengan instalada (opt-in) durante 14 días seguidos**. Recién después se
   habilita *Solicitar acceso a producción*. Las cuentas de organización no tienen
   este requisito.
   - Conseguí 12 o más personas con cuenta de Google (sumá algunas de más por si
     alguna se baja).
   - **Prueba → Pruebas cerradas → Crear pista**, agregá sus emails (o un Grupo
     de Google), subí la versión y compartiles el link de participación.
   - Tienen que aceptar la invitación, instalar la app y **no desinstalarla**
     durante los 14 días. Pediles que la usen y te den comentarios: Google pregunta
     sobre la prueba al solicitar producción.
3. **Crear la app** en Play Console: nombre “Avisame”, idioma Español
   (Latinoamérica), App, Gratis.
4. **Ficha de la tienda**: descripción, ícono 512×512 (exportalo de
   `assets/icono.svg`), gráfico de funciones 1024×500 y capturas.
5. **Contenido de la app** (todo obligatorio):
   - *Política de privacidad*: `https://tu-dominio/privacidad`.
   - *Eliminación de datos*: la app permite borrar la cuenta en **Cuenta → Borrar
     mi cuenta**. Como enlace web para pedir la eliminación sin la app, usá la web
     (`https://tu-dominio` → Cuenta → Borrar mi cuenta).
   - *Seguridad de los datos*: se recopilan email, nombre, número de teléfono,
     ubicación aproximada (ciudad de la búsqueda guardada), fotos e historial de
     compras (automotoras). Se cifran en tránsito, se pueden eliminar, no se
     venden. Se comparten con automotoras solo con consentimiento (nombre y
     teléfono).
   - *Anuncios*: no. *Público objetivo*: mayores de 18. *Clasificación de
     contenido*: completá el cuestionario.
   - *Permisos*: cámara, notificaciones y ubicación aproximada, explicados en la
     app. No pide acceso a toda la galería (usa el selector de fotos de Android).
6. **Subir la versión**: la primera vez subí el `.aab` a mano (Prueba interna o
   cerrada). Después podés usar `npx eas-cli submit -p android` con una cuenta de
   servicio de Google Play.
7. Pasados los 14 días con 12 testers: **Panel → Solicitar acceso a producción**.

---

## 12. Fuentes de vehículos

La tabla `vehiculos` tiene `source`, `external_id` y `external_url` (único por
`source + external_id`), así se pueden sumar fuentes sin tocar el resto:

| `source` | Origen | Estado |
|---|---|---|
| `avisame` | Publicaciones de particulares en la app | Listo |
| `automotora` | Inventario cargado por automotoras (datos completados solos) | Listo |
| `mercadolibre` | **API oficial** de Mercado Libre | Preparado: `_shared/fuentes.ts` convierte ítems de `GET /items/{id}`. Requiere registrar una app en developers.mercadolibre.com.uy y respetar sus términos y límites. |
| `facebook_propio` | Solo el **inventario propio** que el vendedor exporta de su cuenta comercial | Preparado en la base. |

**Nada de scraping** ni de nada que viole los términos de otra plataforma. Las
filas externas se insertan desde el servidor (clave service_role): la app no
puede crear vehículos con esas fuentes (está probado en `test:db`).

---

## 13. Cómo está resuelta la seguridad

- **RLS en todas las tablas.** Cada persona ve y edita solo lo suyo; los
  vehículos activos son públicos.
- **Permisos por columna.** La app no tiene permiso sobre `plan`, `plan_vence`
  ni los datos de Mercado Pago; tampoco puede escribir `coincidencias` ni cambiar
  la fuente de un vehículo.
- **Contacto de clientes**: las automotoras no pueden leer `busquedas`. Ven sus
  clientes con `mis_clientes()` (sin contacto) y piden el contacto con
  `contacto_cliente()`, que verifica en el servidor plan pago vigente,
  consentimiento del cliente y que la búsqueda coincida con un vehículo suyo.
- **Planes**: se activan solo desde `mp-webhook`, con firma verificada y
  consultando el pago en la API de Mercado Pago.
- **Fotos**: cada usuario escribe solo en `fotos/<su id>/`.
- **Ubicación**: nunca filtra resultados; solo ordena y mide distancias en línea
  recta. La del celular no se guarda en el servidor.

---

## 14. Antes de lanzar

- [ ] Completar `EXPO_PUBLIC_RESPONSABLE`, `EXPO_PUBLIC_EMAIL_CONTACTO` y
      `EXPO_PUBLIC_DOMICILIO` (aparecen en la política y los términos).
- [ ] Hacer revisar la política de privacidad y los términos por un profesional.
- [ ] **Inscribir la base de datos** en el Registro de la URCDP (artículo 28 de
      la Ley 18.331): <https://www.gub.uy/urcdp>.
- [ ] SMTP propio para los códigos de ingreso (sección 5).
- [ ] Probar el ciclo completo de Mercado Pago con cuentas de prueba: suscribirse,
      ver el plan activo, cancelar la renovación y ver el historial.
- [ ] Revisar las denuncias periódicamente (tabla `denuncias` en Supabase).
