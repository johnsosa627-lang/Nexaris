/**
 * Recorrido completo en un navegador real (Playwright), contra un servidor ya levantado.
 * Uso:  BASE_URL=http://localhost:3100 SETUP_TOKEN=... node tests/e2e/recorrido.cjs
 * Necesita una base de datos VACÍA (hace la configuración inicial).
 * Guarda capturas de pantalla en SHOTS_DIR (por defecto ./e2e-capturas).
 */
const { chromium } = require("playwright");
const path = require("node:path");
const fs = require("node:fs");

const BASE = process.env.BASE_URL || "http://localhost:3100";
const TOKEN = process.env.SETUP_TOKEN || "codigo-e2e";
const SHOTS = process.env.SHOTS_DIR || path.join(process.cwd(), "e2e-capturas");
fs.mkdirSync(SHOTS, { recursive: true });

const EMAIL = "dueno@prueba.test";
const PASSWORD = "clave-de-prueba-123";
let step = 0;
const errors = [];

function ok(msg) {
  step += 1;
  console.log(`✔ ${step}. ${msg}`);
}

async function expectText(page, text, msg) {
  await page.getByText(text, { exact: false }).filter({ visible: true }).first().waitFor({ timeout: 15000 });
  ok(msg || `Se ve: "${text}"`);
}

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text()}`);
  });
  page.on("dialog", (d) => d.accept());

  try {
    // 1. Sin cuenta todavía: lleva a la configuración inicial
    await page.goto(`${BASE}/empresas`);
    await page.waitForURL("**/configuracion-inicial");
    ok("Sin usuarios, cualquier página lleva a la configuración inicial");

    await page.fill("#setupToken", "codigo-equivocado");
    await page.fill("#workspaceName", "Agencia E2E");
    await page.fill("#name", "John Prueba");
    await page.fill("#email", EMAIL);
    await page.fill("#password", PASSWORD);
    await page.fill("#password2", PASSWORD);
    await page.click("button[type=submit]");
    await expectText(page, "El código de instalación no es correcto", "Rechaza un código de instalación equivocado");

    await page.fill("#setupToken", TOKEN);
    await page.fill("#password", PASSWORD);
    await page.fill("#password2", PASSWORD);
    await page.click("button[type=submit]");
    await page.waitForURL(`${BASE}/`);
    await expectText(page, "Panel principal", "Crea la cuenta del dueño y entra al panel");
    await page.screenshot({ path: path.join(SHOTS, "01-panel-vacio.png"), fullPage: true });

    // 2. Nueva empresa
    await page.goto(`${BASE}/empresas/nueva`);
    await page.fill("#name", "Automotora Real de Prueba");
    await page.fill("#website", "www.automotora-real.example/inicio");
    await page.fill("#sector", "Automotoras");
    await page.fill("#city", "Montevideo");
    await page.click("button[type=submit]");
    await page.waitForURL(/\/empresas\/[0-9a-f-]{36}$/);
    await expectText(page, "automotora-real.example", "Crea la empresa y normaliza el dominio");
    const companyUrl = page.url();

    // 3. Contacto: sin origen es rechazado, con origen se guarda
    await page.click("text=+ Agregar contacto");
    await page.fill("#ct-name", "Laura Gómez");
    await page.fill("#ct-email", "laura@automotora-real.example");
    await page.getByRole("button", { name: "Agregar contacto", exact: true }).click();
    await expectText(page, "Indicá de dónde salió", "Rechaza un email sin origen (no se inventan contactos)");
    await page.selectOption("#source", "sitio_web_empresa");
    await page.fill("#sourceUrl", "https://automotora-real.example/contacto");
    await page.getByRole("button", { name: "Agregar contacto", exact: true }).click();
    await expectText(page, "Contacto agregado.", "Guarda el contacto con su origen");

    // 4. Actividad y seguimiento
    await page.fill("#title", "Llamé a la recepción, pidieron enviar info por email");
    await page.getByRole("button", { name: "Registrar", exact: true }).click();
    await expectText(page, "Actividad registrada.", "Registra una actividad");
    await page.fill("#fu-title", "Enviar diagnóstico a Laura");
    await page.getByRole("button", { name: "Programar", exact: true }).click();
    await expectText(page, "Seguimiento programado.", "Programa un seguimiento");

    // 5. Cambio de etapa
    await page.selectOption("#stage", "contactado");
    await page.getByRole("button", { name: "Cambiar", exact: true }).click();
    await expectText(page, "Etapa: Nuevo → Contactado", "Cambia la etapa y queda en el historial");
    await page.screenshot({ path: path.join(SHOTS, "02-ficha-empresa.png"), fullPage: true });

    // 6. Duplicado por dominio
    await page.goto(`${BASE}/empresas/nueva`);
    await page.fill("#name", "Duplicada");
    await page.fill("#website", "https://automotora-real.example");
    await page.click("button[type=submit]");
    await expectText(page, "Ya existe una empresa con el sitio", "Avisa si la empresa ya está cargada");

    // 7. Datos de prueba + botón de parada + aprobaciones
    await page.goto(`${BASE}/seguridad`);
    await page.getByRole("button", { name: "Cargar datos de prueba", exact: true }).click();
    await expectText(page, "Datos de prueba cargados", "Carga datos de prueba");
    await page.getByRole("button", { name: "Detener todo", exact: true }).click();
    await expectText(page, "Automatizaciones detenidas: ningún agente puede actuar", "El botón de parada muestra el aviso en rojo");

    await page.goto(`${BASE}/aprobaciones`);
    await expectText(page, "PRUEBA: enviar correo de presentación", "La aprobación de prueba está pendiente");
    await page.getByRole("button", { name: "Aprobar", exact: true }).first().click();
    await expectText(page, "no se ejecutó porque las automatizaciones están detenidas", "Aprobar con todo detenido NO ejecuta nada");

    await page.goto(`${BASE}/seguridad`);
    await page.getByRole("button", { name: "Reanudar automatizaciones", exact: true }).click();
    await expectText(page, "Automatizaciones reanudadas", "El dueño puede reanudar");
    await page.screenshot({ path: path.join(SHOTS, "03-seguridad.png"), fullPage: true });

    // 8. Panel con datos, empresas y seguimientos
    await page.goto(`${BASE}/`);
    await expectText(page, "Hay 5 empresa(s) de prueba", "El panel avisa que hay datos de prueba");
    await page.screenshot({ path: path.join(SHOTS, "04-panel-con-datos.png"), fullPage: true });
    await page.goto(`${BASE}/empresas?q=automotora`);
    await expectText(page, "Automotora Real de Prueba", "La búsqueda encuentra empresas");
    await page.goto(`${BASE}/seguimientos`);
    await expectText(page, "Enviar diagnóstico a Laura", "La lista de seguimientos muestra el creado");

    // 9. Agentes
    await page.goto(`${BASE}/agentes`);
    await expectText(page, "Director General AI");
    const cards = await page.getByText("En preparación · Fase").count();
    if (cards !== 12) throw new Error(`Esperaba 12 agentes en preparación, hay ${cards}`);
    ok("Muestra los agentes: 12 en preparación y el Director disponible");

    // 9b. Diagnóstico: sin Director encendido no se puede
    await page.goto(companyUrl);
    await page.getByRole("button", { name: "Analizar sitio web", exact: true }).click();
    await expectText(page, "El Director General está apagado", "Sin el Director encendido no se puede analizar");

    // Encender el Director
    await page.goto(`${BASE}/agentes`);
    const director = page.locator("section", { hasText: "Director General AI" });
    await director.getByText("Configurar").click();
    await director.locator("input[name=enabled]").check();
    await director.getByRole("button", { name: "Guardar", exact: true }).click();
    await expectText(page, "Configuración guardada.", "Enciende el Director");
    await page.reload();
    await director.getByText("Encendido").first().waitFor();
    ok("El Director figura como encendido");
    await page.screenshot({ path: path.join(SHOTS, "05-agentes.png"), fullPage: true });

    // Analizar (el dominio de prueba no existe: el diagnóstico debe decirlo, sin inventar nada)
    await page.goto(companyUrl);
    await page.getByRole("button", { name: "Analizar sitio web", exact: true }).click();
    await page.getByText("No se pudo abrir el sitio web").filter({ visible: true }).first().waitFor({ timeout: 60000 });
    ok("El diagnóstico informa que el sitio no se pudo abrir (la sección se actualizó sola)");
    await expectText(page, "No se pidió resumen a la IA", "No gasta IA en un sitio que no se pudo analizar");

    // Diagnóstico completo preparado por el script de datos (si existe)
    if (process.env.SEED_DATABASE_URL) {
      const richUrl = require("node:child_process")
        .execFileSync("npx", ["tsx", "tests/e2e/sembrar-diagnostico.ts", BASE], {
          env: { ...process.env, NODE_ENV: "test", ANALYZER_ALLOW_PRIVATE: "true", DATABASE_URL: process.env.SEED_DATABASE_URL },
        })
        .toString()
        .trim()
        .split("\n")
        .pop();
      await page.goto(richUrl);
      await expectText(page, "Resumen redactado por IA", "Muestra el resumen de IA");
      await expectText(page, "Hallazgos comprobados", "Muestra los hallazgos comprobados");
      await expectText(page, "Estimaciones (no comprobadas)", "Las estimaciones están separadas y rotuladas");
      await page.getByRole("button", { name: "Agregar como contacto", exact: true }).first().click();
      await expectText(page, "Email publicado en el sitio", "Agrega un email encontrado como contacto, con el sitio como origen");
      await page.screenshot({ path: path.join(SHOTS, "08-diagnostico.png"), fullPage: true });
    }

    // Importar lista
    await page.goto(`${BASE}/empresas/importar`);
    await page.fill("#list", "Nombre\tSitio web\nInmobiliaria Importada Uno\tinmo-importada-1.example\nInmobiliaria Importada Dos\tinmo-importada-2.example\nRepetida\tautomotora-real.example");
    await page.fill("#sector", "Inmobiliarias");
    await page.fill("#city", "Montevideo");
    await page.getByRole("button", { name: "Importar", exact: true }).click();
    await expectText(page, "Se cargaron 2 empresa(s)", "Importa una lista pegada");
    await expectText(page, "Ya existe una empresa con el sitio", "Explica por qué saltea una repetida");

    // Ordenar por puntuación
    await page.goto(`${BASE}/empresas?orden=puntuacion`);
    await page.locator("text=/\\d+\\/100/").first().waitFor();
    ok("La lista muestra la puntuación y se puede ordenar por mejor oportunidad");

    // 10. Celular
    const phone = await browser.newContext({ ...require("playwright").devices["iPhone 13"] });
    await phone.addCookies(await context.cookies());
    const m = await phone.newPage();
    await m.goto(companyUrl);
    await m.locator("li", { hasText: "Laura Gómez" }).first().waitFor();
    const overflow = await m.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (overflow) throw new Error("En el celular la página se desborda hacia el costado");
    ok("En el celular la ficha se ve sin desbordarse");
    await m.screenshot({ path: path.join(SHOTS, "06-celular-ficha.png"), fullPage: true });
    await m.goto(`${BASE}/`);
    await m.getByText("Panel principal").first().waitFor();
    await m.screenshot({ path: path.join(SHOTS, "07-celular-panel.png"), fullPage: true });
    await phone.close();

    // 11. Salir, contraseña equivocada, volver a entrar
    await page.goto(`${BASE}/`);
    await page.getByRole("button", { name: "Salir", exact: true }).last().click();
    await page.waitForURL("**/login");
    ok("Cierra la sesión");
    await page.goto(`${BASE}/seguridad`);
    await page.waitForURL("**/login");
    ok("Sin sesión, las páginas internas mandan al inicio de sesión");
    await page.fill("#email", EMAIL);
    await page.fill("#password", "equivocada");
    await page.click("button[type=submit]");
    await expectText(page, "Email o contraseña incorrectos.", "Rechaza una contraseña equivocada");
    await page.fill("#password", PASSWORD);
    await page.click("button[type=submit]");
    await page.waitForURL(`${BASE}/`);
    ok("Vuelve a entrar con la contraseña correcta");

    // 12. Seguridad de la cookie
    const cookie = (await context.cookies()).find((c) => c.name === "re_session");
    if (!cookie || !cookie.httpOnly || cookie.sameSite !== "Lax") throw new Error("La cookie de sesión no es httpOnly/SameSite=Lax");
    ok("La cookie de sesión no es accesible desde JavaScript (httpOnly) y es SameSite=Lax");
  } catch (err) {
    console.error(`✘ Falló después del paso ${step}: ${err.message}`);
    await page.screenshot({ path: path.join(SHOTS, "error.png"), fullPage: true }).catch(() => {});
    process.exitCode = 1;
  } finally {
    const relevant = errors.filter((e) => !/favicon/.test(e));
    if (relevant.length) {
      console.log("\nErrores en la consola del navegador:");
      for (const e of relevant) console.log("  - " + e);
      process.exitCode = 1;
    } else {
      console.log("\nSin errores en la consola del navegador.");
    }
    await browser.close();
  }
})();
