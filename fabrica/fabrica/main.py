"""Sistema de Ganancias — programa principal. Corre solo, día y noche.

- Cada 15 minutos: baja velas nuevas, revisa la liga (jubila/asciende bots) y actualiza la cuenta de práctica.
- Todas las noches: manda un resumen simple por Telegram.
- Una vez por semana (o con /ciclo): la fábrica inventa y filtra estrategias nuevas.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import ciclo as C
from . import datos as D
from . import liga as L
from .config import DATA_DIR, cargar
from .indicadores import Cache
from .telegram import Telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ganancias")


class Caches:
    """Arma los indicadores solo para las monedas que usan los bots de la liga (ahorra memoria)."""

    def __init__(self):
        self.velas: dict = {}
        self._c: dict = {}

    def poner(self, clave, df):
        self.velas[clave] = df
        self._c.pop(clave, None)

    def get(self, clave, defecto=None):
        if clave not in self.velas:
            return defecto
        if clave not in self._c:
            self._c[clave] = Cache(self.velas[clave])
        return self._c[clave]

    def items(self):
        return ((k, self.get(k)) for k in self.velas)


class Sistema:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.tg = Telegram(cfg["telegram"]["token"], cfg["telegram"]["chat_id"])
        self.liga = L.leer()
        self.caches = Caches()
        self.ciclos_hoy = 0
        self.probadas_hoy = 0
        self.dia_contador = ""
        self.lock = threading.RLock()
        self.ciclo_corriendo = False
        self.fin_ultimo_ciclo = 0.0
        self.ultimo_ciclo: dict | None = None
        self.ultimo_resumen = ""
        self.ultimo_ciclo_dia = ""
        self.tz = ZoneInfo(cfg["agenda"]["zona_horaria"])
        self.tg.comandos = {
            "/start": self.c_ayuda, "/ayuda": self.c_ayuda, "/estado": self.c_estado, "/hoy": self.c_hoy,
            "/bots": self.c_bots, "/fabrica": self.c_fabrica, "/pausar": self.c_pausar,
            "/reanudar": self.c_reanudar, "/cerrar_todo": self.c_cerrar, "/informe": self.c_informe,
            "/ciclo": self.c_ciclo,
        }

    # ---------------- datos ----------------
    def actualizar_datos(self) -> None:
        d = self.cfg["datos"]
        for s in d["simbolos"]:
            for tf in d["temporalidades"]:
                try:
                    df = D.actualizar(s, tf, d.get("desde_por_tf", {}).get(tf, d["desde"]))
                    with self.lock:
                        self.caches.poner((s, tf), df)
                except Exception as ex:
                    log.warning("no se pudieron bajar datos de %s %s: %s", s, tf, ex)

    # ---------------- fábrica ----------------
    def lanzar_ciclo(self) -> str:
        if self.ciclo_corriendo:
            return "La fábrica ya está trabajando. Te aviso cuando termine."
        threading.Thread(target=self._ciclo, daemon=True).start()
        return "🏭 Arrancó la fábrica. Puede tardar un buen rato; te aviso cuando termine."

    def _ciclo(self) -> None:
        self.ciclo_corriendo = True
        try:
            conjuntos = {k: v for k, v in self.caches.velas.items() if len(v) > 2000}
            inf = C.correr_ciclo(self.cfg, conjuntos, avisar=log.info)
            self.ultimo_ciclo = inf
            self.ciclos_hoy += 1
            self.probadas_hoy += inf["embudo"].get("inventadas", 0)
            with self.lock:
                nuevos = L.agregar_candidatos(self.liga, inf["ganadoras"], self.cfg)
                avisos = L.revisar(self.liga, self.caches, self.cfg)
                L.guardar(self.liga)
            continuo = self.cfg["agenda"].get("ciclo_continuo", False)
            if nuevos:
                txt = C.texto_embudo(inf) + f"\n\n🆕 {len(nuevos)} bot(s) nuevo(s) entran como suplentes."
                self.tg.enviar("\n".join([txt] + avisos))
            elif avisos:
                self.tg.enviar("\n".join(avisos))
            elif not continuo:  # en modo 24/7 no se avisa cada vuelta vacía (iría en el resumen de la noche)
                self.tg.enviar(C.texto_embudo(inf))
        except Exception as ex:
            log.exception("falló el ciclo")
            self.tg.enviar(f"⚠️ La fábrica tuvo un error: {type(ex).__name__}. Lo vuelvo a intentar más adelante.")
        finally:
            self.ciclo_corriendo = False
            self.fin_ultimo_ciclo = time.time()

    # ---------------- liga y cuenta ----------------
    def chequeo(self) -> None:
        with self.lock:
            avisos = L.revisar(self.liga, self.caches, self.cfg)
            cuenta = L.cuenta_papel(self.liga, self.caches, self.cfg)
            if cuenta["freno_total"] and not self.liga.get("apagado"):
                self.liga["apagado"] = True
                avisos.append("🛑 FRENO TOTAL: la cuenta de práctica bajó 15 % desde su máximo. "
                              "El sistema dejó de operar. Escribí /reanudar si querés seguir.")
                self.liga.setdefault("pausas", []).append([int(time.time() * 1000), None])
            L.guardar(self.liga)
        if avisos:
            self.tg.enviar("\n".join(avisos))

    # ---------------- comandos ----------------
    def c_ayuda(self) -> str:
        return ("🤖 Sistema de Ganancias\n"
                "/estado – si está prendido y cuánta plata hay\n"
                "/hoy – qué pasó hoy\n"
                "/bots – titulares y suplentes\n"
                "/fabrica – cómo le fue a la fábrica\n"
                "/pausar – frena todo\n"
                "/reanudar – vuelve a operar\n"
                "/cerrar_todo – cierra todo y frena\n"
                "/informe – resumen completo\n"
                "/ciclo – que la fábrica invente estrategias ahora")

    def c_estado(self) -> str:
        with self.lock:
            cu = L.cuenta_papel(self.liga, self.caches, self.cfg)
        est = "⏸️ PAUSADO" if self.liga.get("pausado") else "🛑 APAGADO por freno" if self.liga.get("apagado") else "▶️ PRENDIDO"
        return (f"{est} — modo PRÁCTICA (plata de mentira)\n"
                f"Plata: {cu['capital']} USDT (empezó con {cu['inicial']})\n"
                f"Bots titulares: {len(self.liga['titulares'])} | suplentes: {len(self.liga['suplentes'])}\n"
                f"Fábrica: {'trabajando 🏭' if self.ciclo_corriendo else 'descansando'}")

    def c_hoy(self) -> str:
        with self.lock:
            cu = L.cuenta_papel(self.liga, self.caches, self.cfg)
        if not cu["hoy_ops"]:
            return f"Hoy todavía no hubo operaciones. Plata: {cu['capital']} USDT."
        signo = "ganó" if cu["hoy_usdt"] >= 0 else "perdió"
        return (f"Hoy se hicieron {cu['hoy_ops']} operaciones: {cu['hoy_ganadas']} salieron bien y "
                f"{cu['hoy_ops'] - cu['hoy_ganadas']} mal. En total {signo} {abs(cu['hoy_usdt'])} USDT.\n"
                f"Plata ahora: {cu['capital']} USDT.")

    def c_bots(self) -> str:
        out = []
        for grupo, emoji in (("titulares", "⭐"), ("suplentes", "🪑")):
            out.append(f"{emoji} {grupo.upper()}: {len(self.liga[grupo])}")
            for b in self.liga[grupo]:
                res = L.en_vivo(b, self.caches, self.cfg)
                n = len(res.r) if res is not None else 0
                g = int((res.r > 0).sum()) if n else 0
                e = b["estrategia"]
                out.append(f"• {b['id']} — {e['simbolo'].split(':')[0]} {e['tf']} — confianza {b['puntaje']}/100 — "
                           f"en vivo: {n} ops ({g} bien)\n  {b['explicacion']}")
        if not self.liga["titulares"] and not self.liga["suplentes"]:
            out.append("Todavía no hay bots: la fábrica tiene que encontrar estrategias confiables primero.")
        return "\n".join(out)

    def c_fabrica(self) -> str:
        if self.ciclo_corriendo:
            return "🏭 La fábrica está trabajando ahora mismo."
        if not self.ultimo_ciclo:
            return "La fábrica todavía no terminó ningún ciclo desde que se prendió el sistema."
        return C.texto_embudo(self.ultimo_ciclo)

    def c_pausar(self) -> str:
        with self.lock:
            if not self.liga.get("pausado"):
                self.liga["pausado"] = True
                self.liga.setdefault("pausas", []).append([int(time.time() * 1000), None])
                L.guardar(self.liga)
        return "⏸️ Pausado. Los bots no abren operaciones nuevas. /reanudar para seguir."

    def c_reanudar(self) -> str:
        with self.lock:
            for p in self.liga.get("pausas", []):
                if p[1] is None:
                    p[1] = int(time.time() * 1000)
            self.liga["pausado"] = False
            self.liga["apagado"] = False
            L.guardar(self.liga)
        return "▶️ Listo, el sistema vuelve a operar (en práctica)."

    def c_cerrar(self) -> str:
        self.c_pausar()
        return "🛑 Todo cerrado y pausado (en modo práctica no quedan operaciones reales abiertas). /reanudar para seguir."

    def c_informe(self) -> str:
        return "\n\n".join([self.c_estado(), self.c_fabrica(), self.c_bots()])

    def c_ciclo(self) -> str:
        return self.lanzar_ciclo()

    # ---------------- agenda ----------------
    def resumen_noche(self) -> str:
        with self.lock:
            cu = L.cuenta_papel(self.liga, self.caches, self.cfg)
        dif = round(cu["capital"] - cu["inicial"], 2)
        txt = (f"🌙 Resumen del día\n"
               f"Hoy: {cu['hoy_ops']} operaciones, {cu['hoy_ganadas']} bien. Resultado: {cu['hoy_usdt']} USDT.\n"
               f"Desde el principio: {cu['capital']} USDT ({'+' if dif >= 0 else ''}{dif}).\n"
               f"Bots trabajando: {len(self.liga['titulares'])} titulares, {len(self.liga['suplentes'])} suplentes.\n"
               f"🏭 Fábrica hoy: {self.ciclos_hoy} vueltas, {self.probadas_hoy} estrategias probadas.\n"
               f"Todo en modo práctica.")
        self.ciclos_hoy = self.probadas_hoy = 0
        return txt

    def correr(self) -> None:
        if self.cfg["live"]:
            self.tg.enviar("⚠️ LIVE_TRADING está en true, pero esta versión solo opera en PRÁCTICA. "
                           "La plata real se activa en una etapa posterior.")
        self.tg.enviar("🤖 Sistema de Ganancias prendido. Modo PRÁCTICA (plata de mentira). "
                       "Estoy bajando los datos de Binance; la primera vez tarda un rato.")
        self.tg.escuchar()
        self.actualizar_datos()
        if not self.liga["titulares"] and not self.liga["suplentes"]:
            self.tg.enviar(self.lanzar_ciclo())
        cada = self.cfg["agenda"]["minutos_entre_chequeos"] * 60
        while True:
            try:
                ahora = datetime.now(self.tz)
                hoy = ahora.strftime("%Y-%m-%d")
                if ahora.hour == self.cfg["agenda"]["hora_resumen_noche"] and self.ultimo_resumen != hoy:
                    self.ultimo_resumen = hoy
                    self.tg.enviar(self.resumen_noche())
                ag = self.cfg["agenda"]
                if ag.get("ciclo_continuo", False):
                    # 24/7: apenas termina una vuelta (y pasa la pausa), arranca otra
                    if not self.ciclo_corriendo and time.time() - self.fin_ultimo_ciclo >= ag.get("pausa_entre_ciclos_min", 30) * 60:
                        self.lanzar_ciclo()
                elif ahora.weekday() == ag["dia_ciclo_semanal"] and self.ultimo_ciclo_dia != hoy and ahora.hour >= 3:
                    self.ultimo_ciclo_dia = hoy
                    self.lanzar_ciclo()
                self.chequeo()
            except Exception:
                log.exception("error en el chequeo")
            time.sleep(cada)
            self.actualizar_datos()


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.nice(10)  # prioridad baja: si n8n necesita el procesador, n8n va primero
    except Exception:
        pass
    Sistema(cargar()).correr()


if __name__ == "__main__":
    main()
