"""El servicio que corre 24/7 en Easypanel.

    python -m fabrica.servicio

Variables de entorno (ver .env.example): MODO (papel | testnet | real), LIVE_TRADING,
BINANCE_API_KEY, BINANCE_API_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, FABRICA_DATOS,
FABRICA_RESULTADOS, FABRICA_VIVO.
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from .config import RAIZ, cargar_config
from .datos import tf_ms
from .examen import banco

log = logging.getLogger("fabrica")


class Servicio:
    def __init__(self, cfg: dict, liga, mercado, enviar: Callable[[str], None], reloj: Callable[[], float] = time.time,
                 lanzar_ciclo: Optional[Callable] = None, actualizar_datos: Optional[Callable] = None):
        self.cfg = cfg
        self.S = cfg["servicio"]
        self.liga = liga
        self.mercado = mercado
        self.enviar = enviar
        self.reloj = reloj
        self.tz = ZoneInfo(self.S["zona_horaria"])
        self._lanzar_ciclo = lanzar_ciclo or self._ciclo_en_subproceso
        self._actualizar_datos = actualizar_datos or self._datos_en_hilo
        self.ciclo_en_curso = None
        self.datos_en_curso = None
        self._arranque = True  # al prender: completar los datos que falten, sin esperar al día siguiente
        self._prendida_ms = int(reloj() * 1000)
        self._chequear = False  # chequeo de salud pendiente (después de cada descarga de datos)
        self._procesado = {}
        self._ultima_vigilancia = 0.0
        self._ultimo_radar = 0.0
        self.liga.e.setdefault("tareas", {})
        self.radar = None
        if cfg.get("radar", {}).get("activo"):
            from .radar import Radar
            self.radar = Radar(cfg, self.liga.e, mercado, enviar, reloj)

    # ------------------------------------------------------------------ bucle
    def paso(self):
        self.liga.tick()
        self._velas()
        if self.reloj() - self._ultima_vigilancia >= self.cfg["liga"]["intervalo_vigilancia"]:
            self._ultima_vigilancia = self.reloj()
            self.liga.vigilar()
        if self.radar and self.reloj() - self._ultimo_radar >= self.cfg["radar"]["intervalo_min"] * 60:
            self._ultimo_radar = self.reloj()
            self.radar.revisar()
            self.liga.guardar()
        self._agenda()

    def correr(self):
        while True:
            try:
                self.paso()
            except Exception as e:  # noqa: BLE001
                log.exception("Error en el bucle")
                self.liga._aviso_unico(f"error-{type(e).__name__}", f"⚠️ Error: {str(e)[:300]}")
            time.sleep(5)

    def _velas(self):
        ahora_ms = int(self.reloj() * 1000) - 5_000  # 5 s de margen para que Binance cierre la vela
        for simbolo, tf in sorted(self.liga.mercados()):
            paso = tf_ms(tf)
            cerrada = (ahora_ms // paso) * paso - paso  # inicio de la última vela cerrada
            if self._procesado.get((simbolo, tf), 0) >= cerrada:
                continue
            velas = self.mercado.velas(simbolo, tf, self.cfg["liga"]["velas_historia"], int(self.reloj() * 1000))
            if len(velas) and int(velas["ts"].iloc[-1]) >= cerrada:
                self.liga.procesar_velas(simbolo, tf, velas)
                self._procesado[(simbolo, tf)] = cerrada

    # ------------------------------------------------------------------ agenda
    def _agenda(self):
        t = self.liga.e["tareas"]
        utc = datetime.fromtimestamp(self.reloj(), tz=timezone.utc)
        local = utc.astimezone(self.tz)
        hoy = utc.date().isoformat()

        if self.ciclo_en_curso is not None and self._ciclo_termino():
            self._al_terminar_ciclo()
        if self.datos_en_curso is not None and not self.datos_en_curso.is_alive():
            self.datos_en_curso = None
            self._chequear = True
            log.info("Actualización de datos terminada")

        toca_datos = t.get("datos") != hoy and utc.hour >= self.S["hora_actualizar_datos_utc"]
        if (toca_datos or self._arranque) and self.datos_en_curso is None:
            if toca_datos:
                t["datos"] = hoy
            self._arranque = False
            self.datos_en_curso = self._actualizar_datos()

        if t.get("revision") != hoy and utc.hour >= self.S["hora_revision_utc"]:
            t["revision"] = hoy
            self.liga.revisar()

        semana = f"{utc.isocalendar()[0]}-{utc.isocalendar()[1]}"
        banco_vacio = not banco(self.cfg)
        toca_semanal = utc.weekday() == self.S["dia_ciclo_semanal"] and utc.hour >= self.S["hora_ciclo_utc"]
        # Primer ciclo: si no inventó nada (por ejemplo, faltaban datos), se reintenta una vez por día
        primera_vez = (banco_vacio and not t.get("primer_ciclo_ok") and t.get("primer_ciclo") != hoy
                       and not t.get("ciclo") and self._hay_datos())
        semanal = toca_semanal and t.get("ciclo") != semana
        if self.ciclo_en_curso is None and self.datos_en_curso is None and (semanal or primera_vez):
            if semanal:
                t["ciclo"] = semana
            else:
                t["primer_ciclo"] = hoy
            self._arrancar_ciclo()

        if self._chequear and self.datos_en_curso is None:
            self._chequear = False
            self.chequeo_salud(avisar=True)

        if local.hour >= self.S["hora_resumen"] and t.get("noche") != local.date().isoformat():
            t["noche"] = local.date().isoformat()
            self.enviar(self.liga.texto_noche())
        self.liga.guardar()

    def chequeo_salud(self, avisar: bool = False) -> str:
        """Revisa datos, fábrica y disco. Con avisar=True manda Telegram solo si hay problemas (corre tras cada
        descarga de datos: al prender y una vez por día, así un problema que sigue se recuerda a diario)."""
        from . import salud
        try:
            r = salud.chequeo(self.cfg, int(self.reloj() * 1000), self.ciclo_en_curso is not None, self._prendida_ms,
                              list(self.liga.e["bots"].values()))
        except Exception as e:  # noqa: BLE001 - el chequeo nunca debe frenar el servicio
            log.exception("Falló el chequeo de salud")
            return f"🩺 No pude hacer el chequeo de salud: {e}"
        if avisar and r["problemas"]:
            self.enviar(salud.texto(r, completo=False))
        return salud.texto(r)

    def _arrancar_ciclo(self):
        self.enviar("🏭 Arranca un ciclo de la fábrica: inventar, filtrar y examinar estrategias nuevas. "
                    "Te aviso cuando termine.")
        self.ciclo_en_curso = self._lanzar_ciclo()

    def _inventadas_ultimo_ciclo(self) -> int:
        try:
            with open(os.path.join(self.cfg["salida"]["carpeta"], "ultimo_ciclo.txt"), encoding="utf-8") as f:
                carpeta = os.path.join(self.cfg["salida"]["carpeta"], f.read().strip())
            with open(os.path.join(carpeta, "embudo.json"), encoding="utf-8") as f:
                return int(json.load(f)["embudo"].get("inventadas", 0))
        except (OSError, ValueError, KeyError):
            return 0

    def _motivo_ciclo_vacio(self) -> str:
        try:
            with open(os.path.join(self.cfg["salida"]["carpeta"], "ultimo_ciclo.txt"), encoding="utf-8") as f:
                carpeta = os.path.join(self.cfg["salida"]["carpeta"], f.read().strip())
            with open(os.path.join(carpeta, "embudo.json"), encoding="utf-8") as f:
                mercados = json.load(f).get("por_mercado", [])
        except (OSError, ValueError):
            return "no encontré el detalle del ciclo"
        errores = [f"{m['simbolo'].split('/')[0]} {m['tf']}: {m['error']}" for m in mercados if m.get("error")]
        if not errores:
            return "ningún mercado dio error; revisá /salud"
        return "; ".join(errores[:4]) + (f" (y {len(errores) - 4} más)" if len(errores) > 4 else "")

    def _hay_datos(self) -> bool:
        carpeta = os.path.join(self.cfg["datos"]["carpeta"], "velas")
        return os.path.isdir(carpeta) and len(os.listdir(carpeta)) > 0

    def _ciclo_termino(self) -> bool:
        c = self.ciclo_en_curso
        return c.poll() is not None if hasattr(c, "poll") else not c.is_alive()

    def _al_terminar_ciclo(self):
        proceso, self.ciclo_en_curso = self.ciclo_en_curso, None
        codigo = getattr(proceso, "returncode", 0)
        if codigo:  # el ciclo se cortó: lo que muestre /fabrica sería del ciclo anterior
            self.enviar(f"⚠️ El ciclo de la fábrica se cortó con un error (código {codigo}). El detalle quedó en "
                        "ultimo_ciclo.log. Se vuelve a intentar en el próximo turno; también podés mandar /ciclo.")
            return
        if self._inventadas_ultimo_ciclo() > 0:
            self.liga.e["tareas"]["primer_ciclo_ok"] = True
        else:
            self.enviar("⚠️ Este ciclo no inventó NINGUNA estrategia, así que todo lo demás también da cero. "
                        f"Motivo: {self._motivo_ciclo_vacio()}. Se reintenta solo; también podés mandar /ciclo.")
        nuevos = self.liga.sincronizar_banco(banco(self.cfg))
        self.liga.completar_titulares()
        self.enviar(self.resumen_fabrica() + f"\n\nSe sumaron {len(nuevos)} suplente(s) nuevos a la liga.")
        self.enviar(self.liga.texto_semana() + "\n\n" + self.liga.texto_preparacion())

    def _ciclo_en_subproceso(self):
        carpeta_log = self.liga.carpeta
        os.makedirs(carpeta_log, exist_ok=True)
        salida = open(os.path.join(carpeta_log, "ultimo_ciclo.log"), "w", encoding="utf-8")
        return subprocess.Popen([sys.executable, "-m", "fabrica.ciclo", "--procesos", str(self.S["procesos_ciclo"])],
                                stdout=salida, stderr=subprocess.STDOUT, cwd=str(RAIZ), env=os.environ.copy())

    def _datos_en_hilo(self):
        from .datos import actualizar

        def tarea():
            try:
                actualizar(self.cfg)
            except Exception as e:  # noqa: BLE001
                log.exception("Falló la actualización de datos")
                self.enviar(f"⚠️ No pude actualizar los datos de Binance: {e}")

        hilo = threading.Thread(target=tarea, name="datos", daemon=True)
        hilo.start()
        return hilo

    # ------------------------------------------------------------------ textos
    def resumen_fabrica(self) -> str:
        ruta = os.path.join(self.cfg["salida"]["carpeta"], "ultimo_ciclo.txt")
        if not os.path.exists(ruta):
            estado = "en curso" if self.ciclo_en_curso else "todavía no corrió"
            return f"🏭 La fábrica {estado}. Banco: {len(banco(self.cfg))} estrategias."
        with open(ruta, encoding="utf-8") as f:
            carpeta = os.path.join(self.cfg["salida"]["carpeta"], f.read().strip())
        with open(os.path.join(carpeta, "embudo.json"), encoding="utf-8") as f:
            e = json.load(f)["embudo"]
        examen = os.path.join(carpeta, "informe.txt")
        aprobaron = revision = ""
        if os.path.exists(examen):
            with open(examen, encoding="utf-8") as f:
                renglones = [l.strip() for l in f]
            aprobaron = next((l for l in renglones if l.startswith("Examen final")), "")
            revision = next((l for l in renglones if l.startswith("Revisión con datos nuevos")), "")
        lineas = [f"🏭 Último ciclo de la fábrica ({os.path.basename(carpeta)}):",
                  f"Inventó {e['inventadas']} estrategias; {e['candidatas']} pasaron al colador.",
                  f"Pasaron cada filtro: " + " → ".join(str(e[k]) for k in sorted(e) if k[0].isdigit()), aprobaron,
                  revision,
                  f"Banco total: {len(banco(self.cfg))} estrategias listas.",
                  "Ciclo en curso ahora." if self.ciclo_en_curso else
                  f"Próximo ciclo: el {['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][self.S['dia_ciclo_semanal']]} "
                  f"a las {self.S['hora_ciclo_utc']}:00 UTC."]
        return "\n".join(l for l in lineas if l)

    # ------------------------------------------------------------------ comandos
    def registrar_comandos(self, tg):
        L = self.liga
        tg.registrar("/estado", lambda a: L.texto_estado())
        tg.registrar("/hoy", lambda a: L.texto_hoy())
        tg.registrar("/bots", lambda a: L.texto_bots())
        tg.registrar("/fabrica", lambda a: self.resumen_fabrica())
        tg.registrar("/informe", lambda a: L.texto_semana() + "\n\n" + self.resumen_fabrica() + "\n\n" + L.texto_preparacion())
        tg.registrar("/pausar", self.cmd_pausar)
        tg.registrar("/reanudar", self.cmd_reanudar)
        tg.registrar("/cerrar_todo", self.cmd_cerrar_todo)
        tg.registrar("/confirmar_real", self.cmd_confirmar_real)
        tg.registrar("/ciclo", self.cmd_ciclo)
        tg.registrar("/salud", lambda a: self.chequeo_salud())
        tg.registrar("/diagnostico", self.cmd_diagnostico)
        tg.registrar("/graduacion", lambda a: self.liga.texto_preparacion())
        tg.registrar("/radar", lambda a: self.radar.texto() if self.radar else "El radar externo está apagado (config.yaml).")
        tg.registrar("/ayuda", lambda a: AYUDA)
        tg.registrar("/start", lambda a: AYUDA)

    def cmd_diagnostico(self, a=""):
        """Recalcula las señales de cada bot desde que entró en vivo (en segundo plano: tarda un poco)."""
        from . import diagnostico

        def tarea():
            try:
                bots = [dict(b) for b in self.liga.e["bots"].values()]
                self.enviar(diagnostico.texto(diagnostico.diagnosticar(self.cfg, bots, self.cfg["liga"]["velas_historia"])))
            except Exception as e:  # noqa: BLE001
                log.exception("Falló el diagnóstico")
                self.enviar(f"🔬 No pude hacer el diagnóstico: {e}")
        threading.Thread(target=tarea, name="diagnostico", daemon=True).start()
        return "🔬 Revisando las señales de cada bot. Tarda unos minutos; te mando el resultado."

    def cmd_ciclo(self, a=""):
        """Correr la fábrica ahora (no toca la plata: solo inventa y examina estrategias)."""
        if self.ciclo_en_curso is not None:
            return "🏭 Ya hay un ciclo de la fábrica en curso. Te aviso cuando termine."
        if self.datos_en_curso is not None:
            return "⏳ Estoy bajando los datos de Binance. Probá /ciclo de nuevo en un rato."
        if not self._hay_datos():
            return "Todavía no hay datos de precios para trabajar. Probá más tarde."
        self._arrancar_ciclo()
        return "✅ Listo, la fábrica arrancó (puede tardar varias horas)."

    def cmd_pausar(self, a=""):
        self.liga.e["pausado"] = True
        self.liga.guardar()
        return "⏸ Pausado: los titulares no abren operaciones nuevas. Las abiertas siguen con su stop. Para seguir: /reanudar"

    def cmd_reanudar(self, a=""):
        e = self.liga.e
        if e["apagado"]:
            if a != "confirmo":
                return (f"🛑 El sistema se apagó solo: {e['motivo_apagado']}.\nSi querés volver a prenderlo igual, "
                        "mandá: /reanudar confirmo")
            e.update(apagado=False, motivo_apagado="", pausado=False)
            e["cuenta"]["pico"] = e["cuenta"]["equity"]  # el freno total se mide desde ahora
            self.liga.guardar()
            return f"✅ Prendido de nuevo con {e['cuenta']['equity']:.2f} USDT."
        e["pausado"] = False
        self.liga.guardar()
        return "▶️ Reanudado."

    def cmd_cerrar_todo(self, a=""):
        self.liga.cerrar_todo("cierre manual (/cerrar_todo)")
        self.liga.e["pausado"] = True
        self.liga.guardar()
        return "🧹 Cerré todas las operaciones de los titulares y pausé. Para seguir: /reanudar"

    def cmd_confirmar_real(self, a=""):
        if self.liga.modo != "real":
            return "Esto solo sirve en modo real. Ahora estás en modo " + self.liga.modo + "."
        self.liga.e["real_confirmado"] = True
        self.liga.guardar()
        return "⚠️ Confirmado: los titulares operan con PLATA REAL, empezando con el capital de config.yaml."


AYUDA = ("Comandos:\n/estado — prendido o apagado, plata, práctica o real\n/hoy — resultado de hoy\n"
         "/bots — titulares y suplentes\n/fabrica — qué hizo la fábrica\n/informe — informe semanal\n"
         "/radar — qué pasa fuera del mercado (noticias, datos económicos)\n"
         "/ciclo — correr la fábrica ahora (inventar y examinar estrategias)\n"
         "/salud — chequeo: ¿datos completos? ¿la fábrica trabaja? ¿hay disco?\n"
         "/diagnostico — ¿hubo señales que no se operaron? (revisa cada bot)\n"
         "/graduacion — ¿cuánto falta para poder usar plata real?\n"
         "/pausar — no abrir operaciones nuevas\n/reanudar — seguir\n/cerrar_todo — cerrar todo y pausar")


def configurar_log(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    archivo = RotatingFileHandler(os.path.join(carpeta, "servicio.log"), maxBytes=3_000_000, backupCount=5, encoding="utf-8")
    archivo.setFormatter(fmt)
    consola = logging.StreamHandler()
    consola.setFormatter(fmt)
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.handlers = [archivo, consola]


def main():
    from .ejecutor import EjecutorBinance, Mercado, crear_cliente_privado
    from .liga import Liga
    from .telegram import Telegram
    cfg = cargar_config()
    carpeta_vivo = os.getenv("FABRICA_VIVO") or str(RAIZ / "vivo")
    configurar_log(carpeta_vivo)
    chat = os.getenv("TELEGRAM_CHAT_ID") or str(cfg.get("servicio", {}).get("telegram_chat_id") or "")
    # Un token real nunca tiene "=": si se pegó "TELEGRAM_TOKEN=..." de más, me quedo con lo último
    token = os.getenv("TELEGRAM_TOKEN", "").strip().rsplit("=", 1)[-1].strip()
    tg = Telegram(token, chat.strip().rsplit("=", 1)[-1].strip())
    modo = (os.getenv("MODO") or "papel").strip().lower()
    clave, secreto = os.getenv("BINANCE_API_KEY", ""), os.getenv("BINANCE_API_SECRET", "")
    avisos = []
    if modo not in ("papel", "testnet", "real"):
        avisos.append(f"MODO '{modo}' no existe; uso 'papel'.")
        modo = "papel"
    if modo in ("testnet", "real") and not (clave and secreto):
        avisos.append(f"Faltan las claves de Binance para el modo {modo}: funciono en modo papel (simulado) mientras tanto.")
        modo = "papel"
    ejecutor = None
    if modo in ("testnet", "real"):
        ejecutor = EjecutorBinance(crear_cliente_privado(modo, clave, secreto), cfg["riesgo"]["apalancamiento_max"],
                                   cfg["costos"]["comision_pct"])
    liga = Liga(cfg, carpeta_vivo, Mercado(), ejecutor, tg.enviar, modo=modo)
    if modo == "real" and os.getenv("LIVE_TRADING", "").strip().lower() != "true":
        liga.e.update(apagado=True, motivo_apagado="MODO=real necesita LIVE_TRADING=true en la configuración")
    servicio = Servicio(cfg, liga, liga.mercado, tg.enviar)
    servicio.registrar_comandos(tg)
    tg.iniciar()
    liga.sincronizar_banco(banco(cfg))
    liga.completar_titulares()
    for a in avisos:
        tg.enviar("⚠️ " + a)
    if modo == "real" and not liga.e["real_confirmado"] and not liga.e["apagado"]:
        tg.enviar("⚠️ Modo REAL: antes de operar con plata de verdad, confirmá con /confirmar_real")
    tg.enviar(f"🤖 Fábrica de bots prendida (modo {modo}).\n" + liga.texto_estado() + "\n\n" + AYUDA)
    servicio.correr()


if __name__ == "__main__":
    main()
