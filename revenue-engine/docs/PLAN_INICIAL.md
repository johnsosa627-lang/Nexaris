# Revenue Engine AI — Diagnóstico inicial, arquitectura y plan

Fecha: 8/11/2026 · Estado: **propuesta, esperando autorización** (todavía no hay código).

---

## 1. Qué encontré en el entorno

**Repositorio `Nexaris`** (no se toca nada de lo que ya existe):

| Carpeta / archivo | Qué es | Relación con Revenue Engine |
|---|---|---|
| `fabrica/` | Fábrica de estrategias de trading en Python, corriendo en tu VPS | Ninguna. Sigue igual. |
| `bot-futuros/` | Primer bot de trading (ya no se usa) | Ninguna. |
| `index.html`, `Nexsaris` | Página pública de NEXARIS (GitHub Pages) | Ninguna. |
| `.github/workflows/static.yml` | Publica **todo el repositorio** como página web pública | Ojo: cualquier archivo en este repo queda público. |

**Servidor que ya pagás:** VPS de Hostinger (2 núcleos, 8 GB de RAM) con Easypanel, donde corren la fábrica y n8n. La fábrica ya tuvo procesos que murieron por falta de memoria, así que hay que poner límites de memoria a todo lo nuevo.

**Herramientas disponibles en el entorno de desarrollo:** Node 22, pnpm, Python 3.13, Docker, cliente de PostgreSQL 16, Chromium + Playwright (para pruebas y para analizar sitios web). Todo lo necesario para construir y probar está.

**Conexiones:** el conector de n8n falló al conectarse en esta sesión; Stripe necesita autorización. Ninguna de las dos hace falta para el MVP.

---

## 2. Arquitectura propuesta

### Idea central

No son 12 programas de IA conversando entre sí sin control. Es **una sola aplicación** con:

1. **Agentes** = módulos con una tarea concreta, herramientas permitidas, un modelo de IA asignado y un registro de cada ejecución (qué recibió, qué produjo, cuánto costó, en qué evidencia se basó).
2. **Director General** = el coordinador: lee la situación de una empresa, arma un plan de tareas, se las asigna a los agentes y revisa resultados contra objetivos. Cada decisión queda guardada con su explicación.
3. **Portero de acciones** (el corazón de la seguridad): **toda** acción que sale hacia afuera pasa por él. Clasifica en Nivel 1 (automático), Nivel 2 (requiere tu aprobación) o Nivel 3 (restringida, aprobación explícita + límites). Revisa el botón de parada antes de ejecutar cualquier cosa.
4. **Capa de integraciones** = cada servicio externo (Gmail, Shopify, Mercado Pago…) es un "conector" con la misma forma: conectar, probar, sincronizar, estado, permisos, último error. Agregar uno nuevo no obliga a rehacer nada.

```
 Navegador (panel en español) ──► Aplicación Next.js ──► PostgreSQL
                                     │   ├─ CRM, finanzas, informes
                                     │   ├─ Director + agentes
                                     │   ├─ Portero de acciones (niveles 1/2/3, botón de parada)
                                     │   └─ Cola de tareas (dentro de PostgreSQL)
                                     └──► Conectores ──► APIs oficiales (Claude, Google, Gmail, Mercado Pago…)
```

### Reglas que el sistema impone por diseño (no por buena voluntad)

- **Hechos vs. estimaciones:** cada hallazgo se guarda con un tipo (`hecho comprobado`, `estimación`, `hipótesis`), su fuente (URL o API + fecha) y su nivel de confianza. Los informes los muestran separados.
- **Sin evidencia no hay resultado:** el Director no puede registrar "esto generó ventas" si no hay una métrica medida y vinculada.
- **Comisiones:** solo se facturan las marcadas como `atribución comprobada`; las demás se muestran como estimación.
- **Pagos:** un pago solo pasa a "recibido" cuando el proveedor (Mercado Pago, etc.) lo confirma.
- **Separación de clientes:** cada fila de la base de datos lleva el identificador de su empresa y todo acceso pasa por una capa que filtra por empresa (más adelante se refuerza con seguridad a nivel de fila de PostgreSQL).
- **Claves:** en variables de entorno del servidor; los tokens de Gmail/Google se guardan cifrados. Nunca llegan al navegador.

### Tecnologías elegidas (solo las necesarias)

| Tecnología | Para qué | Costo |
|---|---|---|
| **Next.js + TypeScript** | Panel web y servidor en un solo proyecto | Gratis |
| **PostgreSQL** (en tu VPS, vía Easypanel) | Base de datos de todo: CRM, finanzas, historial, cola de tareas | Gratis (ya pagás el VPS) |
| **Drizzle** (librería) | Hablar con la base de datos de forma segura y con migraciones | Gratis |
| **Auth.js** | Inicio de sesión, roles (vos, equipo, cliente) | Gratis |
| **pg-boss** | Cola de tareas en PostgreSQL (evita sumar Redis) | Gratis |
| **API de Claude (Anthropic)** | Redactar diagnósticos, propuestas, correos, análisis | Pago por uso (ver abajo) |
| **Google PageSpeed Insights API** | Velocidad y calidad técnica de sitios web | Gratis |
| **Playwright/Chromium** | Leer sitios web como un navegador real (solo páginas públicas, respetando robots.txt) | Gratis |

**Lo que NO uso al principio y por qué:**
- **Supabase:** útil, pero agrega un proveedor externo y su plan gratis se pausa por inactividad. PostgreSQL propio cumple igual y es tuyo.
- **Python:** la fábrica ya lo usa, pero el MVP no lo necesita. Se suma solo si un análisis lo pide (por ejemplo, estadística avanzada para experimentos).
- **n8n:** ya lo tenés. Sirve para conectar cosas sueltas más adelante, pero la lógica de aprobaciones y seguridad tiene que vivir dentro de la aplicación, no repartida en flujos.
- **Redis, Kubernetes, microservicios:** innecesarios a esta escala.

---

## 3. Costos iniciales y dependencias

### Costos mensuales estimados al empezar

| Concepto | Costo |
|---|---|
| Servidor (VPS actual) | US$ 0 adicional |
| Base de datos, login, cola | US$ 0 |
| Dominio propio (opcional, ej. `revenueengine.uy`) | ~US$ 10–40 al año |
| API de Claude | ~US$ 15–30 por cada 100 empresas analizadas |
| Copias de seguridad fuera del servidor | ~US$ 0–2 |
| **Total aproximado** | **US$ 15–35 al mes** con 100 diagnósticos |

**Detalle del costo de IA** (precios vigentes por millón de tokens):

| Modelo | Entrada | Salida | Uso propuesto |
|---|---|---|---|
| Claude Opus 5.5 | US$ 4 | US$ 20 | Diagnósticos, propuestas, Director (calidad alta) |
| Claude Sonnet 5.5 | US$ 2 | US$ 10 | Alternativa más barata si la calidad alcanza |
| Claude Haiku 5.5 | US$ 0,10 | US$ 0,50 | Clasificar respuestas, tareas simples |

Un diagnóstico usa aproximadamente 15.000 tokens de entrada y 3.000–6.000 de salida: **unos US$ 0,15–0,25 con Opus**, menos de la mitad con Sonnet. Los análisis que no son urgentes pueden ir por lotes (50% más barato). El sistema registra el costo real de cada ejecución y tendrá un **tope mensual de gasto en IA** que vos definís.

### Qué depende de cuentas, permisos o terceros

| Necesidad | Qué hace falta | ¿Bloquea el MVP? |
|---|---|---|
| IA | Clave de API de Anthropic (console.anthropic.com) con tarjeta | **Sí** |
| Buscar empresas automáticamente | Clave de Google Places API (tiene cuota gratis mensual, después cobra por consulta) | No: se puede cargar empresas a mano o por planilla |
| Enviar correos desde Gmail | Proyecto en Google Cloud + permiso OAuth `gmail.send`. Para uso propio alcanza el "modo prueba" (hasta 100 usuarios, pero el permiso vence cada 7 días); con una cuenta de Google Workspace se evita ese límite. Leer respuestas requiere permisos "restringidos" que Google audita si la app es pública. | No: en la primera versión el correo se copia y se envía a mano |
| Cobrar | Cuenta de Mercado Pago (disponible en Uruguay). **Stripe:** hasta donde sé no abre cuentas a empresas uruguayas; habría que verificarlo o usar una empresa en otro país. | No (Fase 5) |
| Facturación legal en Uruguay | La DGI exige factura electrónica (CFE) mediante un proveedor habilitado | No (Fase 5) |
| Google Ads, Meta Ads, Search Console, Analytics, Business Profile | Acceso del cliente a sus cuentas; Google Ads además pide un "developer token" aprobado | No (Fases 3–6) |
| Amazon, Mercado Libre, Shopify, WooCommerce | Registrar una app en cada plataforma y que el vendedor la autorice | No (Fase 3+) |
| WhatsApp Business | Proveedor oficial de Meta (con costo por conversación) | No (Fase 6) |

### Legal (para consultar con un profesional antes de enviar correos)

- En Uruguay rige la **Ley 18.331 de Protección de Datos Personales**. Un correo como `juan@empresa.com` es un dato personal. Si contactás empresas de la Unión Europea, aplica además el RGPD.
- Por eso el sistema solo guardará contactos **publicados por la propia empresa** (su sitio web, su ficha pública), registrará de dónde salió cada dato, incluirá siempre una forma de darse de baja y respetará una **lista de exclusión** que no se puede saltear.
- Nada de envíos masivos: tope diario configurable y cada correo aprobado por vos.

---

## 4. El MVP más chico que se puede probar con empresas reales

**Nombre:** *Captación con diagnóstico*. Un país (Uruguay) y un sector (a elegir, ej. inmobiliarias o automotoras de Montevideo).

**Qué hace, paso a paso:**

1. **Entrás con usuario y contraseña** al panel (solo vos al principio).
2. **Cargás empresas**: a mano, desde una planilla, o (si das la clave) buscándolas en Google Places por sector y ciudad.
3. **El analizador revisa el sitio web público** de cada una y registra hechos comprobables, por ejemplo: si tiene HTTPS, si se ve bien en el celular, puntaje de velocidad, título y descripción para Google, botón de WhatsApp, formulario de contacto, teléfono visible, píxel de Meta o Google Analytics instalado, redes sociales enlazadas, reseñas y puntaje en Google (si hay clave).
4. **La IA redacta un diagnóstico** separando "lo que comprobamos" de "lo que estimamos", con la fuente de cada dato.
5. **Puntuación de oportunidad (0–100)** con fórmula visible: cuántos problemas solucionables tiene, tamaño aparente, si invierte en publicidad, si tiene forma de contacto, etc. Ves por qué cada empresa tiene su puntaje.
6. **Borrador de correo y propuesta** personalizados que mencionan un problema real y verificable de esa empresa.
7. **Cola de aprobación**: nada sale sin tu "aprobar". En esta primera versión copiás el correo y lo enviás vos; la conexión con Gmail es el paso siguiente.
8. **CRM básico**: ficha de cada empresa con contactos, diagnóstico, correos, respuestas, etapa (prospecto → contactado → respondió → reunión → propuesta → cliente / descartado), próximos seguimientos e historial completo.
9. **Panel principal** con prospectos nuevos, oportunidades, seguimientos pendientes, alertas y costo de IA del mes.
10. **Seguridad desde el día uno**: registro de toda actividad, niveles de autonomía, botón para detener todo, lista de exclusión, tope de gasto de IA.

**Qué vamos a poder demostrar con el MVP:**
- Que en minutos el sistema produce un diagnóstico **verificable** de una empresa real (cualquiera puede abrir su sitio y comprobarlo).
- Qué empresas priorizar y por qué.
- La tasa real de respuesta y de reuniones conseguidas con correos personalizados (medida, no estimada).
- El costo real por empresa analizada y por reunión conseguida.

**Qué NO va a demostrar todavía:** que la plataforma aumenta las ventas de un cliente. Eso requiere un cliente activo, acceso a sus datos y semanas de medición (Fases 4–5). No lo vamos a afirmar antes.

---

## 5. Plan de trabajo por etapas

Cada etapa termina con pruebas automáticas, una prueba manual guiada para vos y documentación de cómo usarla.

| Etapa | Contenido | Necesita de vos |
|---|---|---|
| **1A — Base** | Proyecto, base de datos, inicio de sesión, panel principal, registro de empresas y contactos, CRM básico con etapas e historial, registro de actividad, niveles de autonomía, botón de parada, pantalla de configuración de agentes. Datos de prueba marcados como tales. | Aprobar este plan |
| **1B — Diagnóstico** | Analizador de sitios web, PageSpeed, diagnóstico con IA (hechos vs. estimaciones), puntuación de oportunidad, tope de gasto de IA. | Clave de Anthropic |
| **1C — Contacto** | Borradores de correo y propuesta, cola de aprobación, lista de exclusión, seguimientos programados, registro de respuestas a mano. **Primera prueba con 20–30 empresas reales.** | Elegir sector; revisar el texto legal de baja |
| **2 — Captación completa** | Búsqueda con Google Places, conexión Gmail (enviar con aprobación, detectar respuestas), clasificación de interesados con IA, propuesta en PDF. | Clave de Google Places; proyecto Google Cloud |
| **3 — Inteligencia comercial** | Competidores, SEO, conversión de sitios, productos y tiendas, conectores de Search Console / Analytics / Business Profile / Shopify. | Acceso a cuentas de un cliente piloto |
| **4 — Clientes y resultados** | Portal privado por cliente, informes semanales/mensuales en PDF, indicadores, experimentos con reglas estadísticas (muestra mínima, sin declarar ganadores antes de tiempo). | Un cliente piloto |
| **5 — Finanzas** | Planes y precios por país/moneda, suscripciones, comisiones con baseline y fórmula guardada, pagos con Mercado Pago, gastos, rentabilidad por cliente y servicio, exportación contable, avisos de vencimiento. | Cuenta Mercado Pago; consulta con contador |
| **6 — Automatizaciones** | Director coordinando agentes en ciclos, Email Engine completo, campañas (Google/Meta Ads con límites de gasto), recuperación de clientes, WhatsApp. | Cuentas de publicidad y aprobaciones |
| **7 — Escala** | Más países, sectores, idiomas y monedas; optimización de costos. | — |

El modelo de datos de la Etapa 1A ya contempla las fases siguientes (empresas, contratos, pagos, comisiones, experimentos, conectores), para no tener que rehacer la base después.

---

## 6. Decisiones pendientes

1. **¿Aprobás la arquitectura y las tecnologías?**
2. **¿Dónde vive el código?** Recomiendo un **repositorio nuevo y privado** (`revenue-engine`), porque este repo se publica entero como página web y el código de un producto comercial no debería ser público. Lo tendrías que crear vos en GitHub (yo no puedo crear repositorios desde aquí). Mientras tanto puedo trabajar en la carpeta `revenue-engine/` de este repo.
3. **¿Dónde corre?** Recomiendo tu VPS actual (sin costo extra) con límite de memoria, y pasar a uno propio cuando haya clientes pagando.
4. **¿Qué sector y ciudad para la primera prueba real?**
5. **¿Tenés o podés crear la clave de API de Anthropic?** (Hace falta desde la Etapa 1B.)
