# Revenue Engine AI

Plataforma de inteligencia comercial: captar empresas, organizar el CRM, coordinar agentes de IA con
límites de seguridad y medir resultados reales. El plan completo está en [`docs/PLAN_INICIAL.md`](docs/PLAN_INICIAL.md).

## Estado

### Etapa 1B — Diagnóstico ✅

| Qué | Estado |
|---|---|
| Análisis del sitio web (página principal): https, celular, Google, medición, publicidad, contacto, redes, plataforma | ✅ |
| Hallazgos **comprobados** con evidencia (qué se vio y dónde) | ✅ |
| Puntuación de oportunidad 0-100 con fórmula visible (necesidad, inversión, contactabilidad) | ✅ |
| Resumen comercial con Claude: cada punto debe citar un hallazgo real; lo que no, se descarta | ✅ probado con IA simulada · falta probar con la clave real |
| Estimaciones separadas y rotuladas "Estimación" | ✅ |
| Tope mensual de gasto de IA (general y del Director) y costo real de cada análisis | ✅ |
| Cola en segundo plano (de a uno, retoma si el servidor se reinicia, respeta el botón de parada) | ✅ |
| Emails publicados en el sitio → "Agregar como contacto" con el sitio como origen | ✅ |
| Importar listas de empresas pegando desde una planilla | ✅ |
| Respeta robots.txt; nunca accede a la red interna del servidor | ✅ |
| Google PageSpeed (velocidad oficial) | ✅ opcional, con `PAGESPEED_API_KEY` |

**Límites honestos:** solo se analiza la página principal; una medición de velocidad es puntual; la puntuación
prioriza a quién contactar pero no predice ventas.

### Etapa 1A — Base funcional ✅

| Qué | Estado |
|---|---|
| Inicio de sesión seguro (contraseñas cifradas, bloqueo tras 5 intentos fallidos, sesiones de 14 días) | ✅ |
| Configuración inicial protegida con código (`SETUP_TOKEN`) | ✅ |
| Panel principal (clientes, prospectos, oportunidades, seguimientos, aprobaciones, alertas) | ✅ |
| CRM: empresas, contactos con origen obligatorio, actividad, etapas, seguimientos, historial | ✅ |
| Detección de empresas duplicadas por sitio web | ✅ |
| Niveles de autonomía 1/2/3 con mínimos que no se pueden bajar | ✅ |
| Cola de aprobaciones (Nivel 3 solo el dueño, escribiendo AUTORIZO) | ✅ |
| Botón de parada de automatizaciones | ✅ |
| Lista de exclusión (emails y dominios) y registro de bajas | ✅ |
| Registro de actividad de todo (solo se agrega, no se edita) | ✅ |
| Límites de gasto de IA y de correos por día | ✅ guardados · se aplican desde 1B/2 |
| Configuración de los 13 agentes (modelo, presupuesto, instrucciones) | ✅ · ninguno se puede encender todavía |
| Datos de prueba marcados "PRUEBA" que se borran de una vez | ✅ |
| Ingresos, comisiones, resultados | Muestra "Sin datos" (Fases 4–5): no se inventan números |

**Lo que todavía NO hace (a propósito):** ningún agente usa IA aún, no envía correos, no se conecta a
servicios externos. Si una acción se aprueba y no hay integración conectada, el sistema lo dice
claramente: *"no se realizó nada fuera del sistema"*.

## Cómo instalarlo en tu VPS (Easypanel)

1. **Base de datos:** en Easypanel → tu proyecto → *+ Servicio* → **Postgres**. Nombre: `revenue-db`.
   Copiá la "Internal connection URL" que te muestra.
2. **Aplicación:** *+ Servicio* → **App**. Nombre: `revenue-engine`.
   - Fuente: GitHub `johnsosa627-lang/Nexaris`, rama `main`, ruta de compilación `/revenue-engine`, tipo **Dockerfile**.
3. **Variables de entorno** de la app (pestaña *Environment*):
   ```
   DATABASE_URL=<la Internal connection URL del paso 1>
   SETUP_TOKEN=<inventá un código largo>
   ENCRYPTION_KEY=<32 bytes en base64, ver abajo>
   ANTHROPIC_API_KEY=<tu clave de console.anthropic.com>
   PAGESPEED_API_KEY=<opcional, gratis en Google Cloud>
   ```
   Para `ENCRYPTION_KEY` puedo generarte uno; o en la Consola web de Hostinger: `openssl rand -base64 32`.
4. **Dominio:** pestaña *Domains* → agregar uno (ej. `app.tudominio.com`) con HTTPS activado, puerto `3000`.
5. **Deploy.** Al arrancar, la app pone la base de datos al día sola.
6. Abrí el dominio: te va a pedir la **configuración inicial**. Escribí el `SETUP_TOKEN`, tus datos y una contraseña de 10+ caracteres.
7. En *Agentes* encendé el **Director General** (es quien coordina los diagnósticos). En *Seguridad → Límites* revisá el tope mensual de IA (por defecto US$30).
8. Opcional: en *Seguridad → Datos de prueba* podés cargar empresas inventadas para practicar y después borrarlas.

**Memoria:** la imagen limita a Node a ~384 MB para no afectar a la fábrica ni a n8n. En Easypanel
también podés poner un límite de memoria al servicio (*Resources*), por ejemplo 600 MB.

**HTTPS es necesario:** la cookie de sesión solo viaja por conexiones seguras. Si probás sin HTTPS,
agregá `COOKIE_SECURE=false` (solo para pruebas).

## Copias de seguridad

- Easypanel ofrece copias de seguridad para sus servicios Postgres (revisá la pestaña *Backups* del servicio `revenue-db`; conviene enviarlas a un almacenamiento externo).
- Alternativa: `scripts/backup.sh` crea una copia comprimida y guarda las últimas 14.
- Una copia que vive en el mismo servidor no sirve si el servidor se pierde: guardala también afuera.

## Para desarrolladores

Requisitos: Node 22 y PostgreSQL 16.

```bash
cp .env.example .env          # completar DATABASE_URL, SETUP_TOKEN, ENCRYPTION_KEY (+ COOKIE_SECURE=false en local)
npm install
npm run db:migrate            # crea las tablas
npm run dev                   # http://localhost:3000
```

| Comando | Qué hace |
|---|---|
| `npm test` | Pruebas automáticas (necesita una base `revenue_engine_test`; ver `TEST_DATABASE_URL`) |
| `npm run typecheck` / `npm run lint` | Revisión de tipos y estilo |
| `node tests/e2e/recorrido.cjs` | Recorrido en navegador real contra un servidor levantado con base vacía (`BASE_URL`, `SETUP_TOKEN`) |
| `npm run db:generate` | Genera una migración nueva después de cambiar `src/db/schema.ts` |

### Estructura

```
src/
  db/schema.ts        Tablas (todas con workspaceId: separación de datos)
  lib/catalog.ts      Etapas, tipos de acción y sus niveles mínimos, agentes, modelos de IA
  i18n/               Textos (español); para otro idioma se agrega un archivo
  server/             Lógica de negocio. Cada función recibe el contexto y filtra por espacio de trabajo
    gateway.ts        Portero de acciones: niveles, aprobaciones, botón de parada, ejecutores
    security.ts       Parada, niveles, límites, lista de exclusión, registro
    crm.ts            Empresas, contactos, actividad, seguimientos, panel
    auth.ts           Configuración inicial, inicio de sesión, sesiones
    agents.ts         Configuración de agentes
  app/                Pantallas (Next.js)
tests/                Pruebas automáticas + recorrido en navegador
drizzle/              Migraciones de la base de datos
```

### Decisiones técnicas

- **Inicio de sesión propio** (en vez de Auth.js, que figuraba en el plan): son ~150 líneas con `scrypt` de Node, tokens aleatorios guardados como hash y cookie `httpOnly`. No suma dependencias y está cubierto por pruebas.
- **Cola propia en PostgreSQL** (en vez de `pg-boss`): los diagnósticos se toman con `FOR UPDATE SKIP LOCKED`; el trabajador corre dentro del mismo servidor (`src/instrumentation.ts`). Si más adelante hay muchos tipos de tareas, se evalúa `pg-boss`.
- **Seguridad del analizador:** solo puertos 80/443, bloqueo de redes internas en el momento de conectar (también IPs escritas directo), 3 MB y 15 s como máximo, 5 redirecciones.
- **Los catálogos viven en el código:** nadie puede bajar el nivel mínimo de una acción tocando la base de datos.
- **Hora de Uruguay (UTC-3)** para fechas que escribe la persona.
