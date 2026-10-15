"""La liga de bots: titulares (operan) y suplentes (practican en paralelo con plata de mentira).

- Titulares: hasta N, que no se parezcan entre sí (correlación < 0,5) y uno por moneda.
  En modo testnet operan en la cuenta Demo de Binance; en modo papel, simulados.
- Suplentes: SIEMPRE simulados con precios reales (Binance permite una sola posición por moneda
  en una cuenta, así que no pueden compartir la cuenta con los titulares).
- Ascenso: un suplente reemplaza a un titular solo con suficientes operaciones en vivo y siendo
  claramente mejor (prueba estadística, no una racha).
- Jubilación: si la caída en vivo supera la peor prevista por Monte Carlo, o si los resultados
  se alejan mucho de lo que prometía el backtest.
- Protección de la cuenta: 1% de riesgo por operación, 3% abierto total, freno diario y freno total.
"""
import csv
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import pandas as pd

from . import cuenta as C
from .bots import (cierre_de_vela, distancia_rango, niveles, resultado, revisar_vela, senal_contraria,
                   senal_ultima_vela, usa_externos)
from .datos import tf_ms

log = logging.getLogger("fabrica")

COLUMNAS_CSV = ["fecha", "bot", "rol", "modo", "simbolo", "tf", "lado", "entrada", "salida", "cantidad",
                "r", "pnl_usdt", "motivo"]


def _moneda(simbolo):
    return simbolo.split("/")[0]


class Liga:
    def __init__(self, cfg: dict, carpeta: str, mercado, ejecutor=None, notificar: Callable[[str], None] = print,
                 reloj: Callable[[], float] = time.time, modo: str = "papel"):
        self.cfg = cfg
        self.L = cfg["liga"]
        self.R = cfg["riesgo"]
        self.carpeta = carpeta
        self.mercado = mercado
        self.ejecutor = ejecutor          # solo para titulares en testnet/real
        self.notificar = notificar
        self.reloj = reloj
        self.modo = modo
        c = cfg["costos"]
        self.comision, self.slippage = c["comision_pct"] / 100, c["slippage_pct"] / 100
        self.slip_stop = c.get("slippage_stop_pct", 0.03) / 100
        self.riesgo_frac = self.R["riesgo_por_operacion_pct"] / 100
        self.ruta = os.path.join(carpeta, "estado_liga.json")
        self.ruta_csv = os.path.join(carpeta, "operaciones.csv")
        self._avisos = {}
        capital = float(self.R["capital_inicial"])
        self.e = {"bots": {}, "pausado": False, "apagado": False, "motivo_apagado": "", "real_confirmado": False,
                  "cuenta": {"equity": capital, "pico": capital, "dia": "", "inicio_dia": capital,
                             "pnl_hoy": 0.0, "racha_hoy": 0, "freno_dia": ""}, "eventos": []}
        if os.path.exists(self.ruta):
            with open(self.ruta, encoding="utf-8") as f:
                guardado = json.load(f)
            self.e.update(guardado)

    # ------------------------------------------------------------------ utilidades
    def guardar(self):
        os.makedirs(self.carpeta, exist_ok=True)
        tmp = self.ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.e, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.ruta)

    def ahora(self) -> datetime:
        return datetime.fromtimestamp(self.reloj(), tz=timezone.utc)

    def hoy(self) -> str:
        return self.ahora().date().isoformat()

    def evento(self, texto: str, avisar: bool = True):
        self.e["eventos"] = (self.e["eventos"] + [{"fecha": self.ahora().isoformat(timespec="seconds"), "texto": texto}])[-300:]
        log.info(texto.replace("\n", " | "))
        if avisar:
            self.notificar(texto)

    def _aviso_unico(self, clave: str, texto: str):
        """Avisa una sola vez por día por cada tema (para no llenar Telegram)."""
        if self._avisos.get(clave) != self.hoy():
            self._avisos[clave] = self.hoy()
            self.evento(texto)

    def bots(self, rol: Optional[str] = None) -> list:
        return [b for b in self.e["bots"].values() if rol is None or b["rol"] == rol]

    def con_dinero(self, bot) -> bool:
        return bot["rol"] == "titular" and self.ejecutor is not None

    def capital(self) -> float:
        return C.capital_base(float(self.R["capital_inicial"]), self.e["cuenta"]["equity"])

    def retornos_bt(self, bot) -> list:
        if bot.get("r_backtest"):
            return [r * self.riesgo_frac for r in bot["r_backtest"]]
        return bot.get("retornos_backtest", [])

    # ------------------------------------------------------------------ banco y titulares
    def sincronizar_banco(self, registros: list) -> list:
        nuevos = []
        for reg in registros:
            if reg["id"] in self.e["bots"]:
                continue
            if len(self.bots("suplente")) >= self.L["max_suplentes"]:
                break
            self.e["bots"][reg["id"]] = {
                "id": reg["id"], "rol": "suplente", "simbolo": reg["simbolo"], "tf": reg["tf"],
                "estrategia": reg["estrategia"], "explicacion": reg.get("explicacion", ""),
                "fitness": reg.get("fitness", 0.0), "nivel": reg.get("nivel", "estricto"),
                "mc_dd": (reg.get("montecarlo") or {}).get("drawdown_p95_pct", self.cfg["filtros"]["max_drawdown_pct"]),
                "r_backtest": reg.get("r_backtest", []), "retornos_backtest": reg.get("retornos_backtest", []),
                "retornos_diarios": reg.get("retornos_diarios", {}),
                "posicion": None, "trades": [], "ultima_vela_ts": 0,
                "desde": self.ahora().isoformat(timespec="seconds"), "motivo_jubilacion": ""}
            nuevos.append(reg["id"])
        if nuevos:
            self.evento(f"🆕 {len(nuevos)} estrategia(s) nueva(s) del banco entran como suplentes.", avisar=False)
        self.guardar()
        return nuevos

    def elegible(self, bot, excluir: Optional[str] = None) -> bool:
        if bot["rol"] != "suplente" or bot["posicion"] is not None:
            return False
        if bot.get("nivel") == "exploracion" and self.modo == "real":
            return False  # las de filtros flojos NUNCA operan con plata real
        if bot.get("no_operable") or not self.operable(bot):
            return False  # con este capital no llega al mínimo de Binance: no ocupa un lugar de titular
        titulares = [t for t in self.bots("titular") if t["id"] != excluir]
        if any(t["simbolo"] == bot["simbolo"] for t in titulares):
            return False  # una sola posición por moneda en la cuenta
        if any(abs(C.correlacion(bot["retornos_diarios"], t["retornos_diarios"])) >= self.L["max_correlacion"]
               for t in titulares):
            return False
        return not self.debe_jubilarse(bot)[0]

    def operable(self, bot) -> bool:
        """¿Puede operar con el capital actual respetando el 1% de riesgo y el mínimo de Binance?"""
        try:
            _, min_nocional = self.mercado.limites(bot["simbolo"])
        except Exception:  # noqa: BLE001 - sin datos del mercado no se descarta
            return True
        if not min_nocional:
            return True
        capital = self.capital()
        maximo = capital * self.R["apalancamiento_max"]
        if min_nocional > maximo:
            return False
        s = bot["estrategia"]["salidas"]
        if s["stop_tipo"] == "pct":  # con stop en %, el tamaño de la operación se sabe de antemano
            return min(capital * self.riesgo_frac / (s["stop"] / 100), maximo) >= min_nocional
        return True  # stop en ATR: depende del momento; si no alcanza, lo detecta al operar

    def completar_titulares(self):
        # Primero las que pasaron los filtros estrictos; las de exploración solo si sobra lugar
        candidatos = sorted(self.bots("suplente"), key=lambda b: (b.get("nivel") != "exploracion", b["fitness"]),
                            reverse=True)
        for bot in candidatos:
            if len(self.bots("titular")) >= self.L["max_titulares"]:
                break
            if self.elegible(bot):
                self._ascender(bot, "lugar libre en el equipo titular")
        self.guardar()

    def _ascender(self, bot, motivo):
        bot["rol"] = "titular"
        bot["titular_desde"] = self.ahora().isoformat(timespec="seconds")
        if self.ejecutor is not None:
            self.ejecutor.preparar(bot["simbolo"])
        prueba = " 🧪 (en prueba: filtros flojos, solo práctica)" if bot.get("nivel") == "exploracion" else ""
        self.evento(f"⬆️ {bot['id']} ({_moneda(bot['simbolo'])} {bot['tf']}) pasa a TITULAR{prueba}: {motivo}.\n"
                    f"Qué hace: {bot['explicacion']}")

    def debe_jubilarse(self, bot):
        rets = [t["retorno"] for t in bot["trades"]]
        if not rets:
            return False, ""
        dd = C.drawdown_pct(rets)
        if dd > bot["mc_dd"]:
            return True, f"su caída en vivo ({dd:.1f}%) superó la peor que había previsto Monte Carlo ({bot['mc_dd']:.1f}%)"
        if len(rets) >= self.L["min_operaciones_control"]:
            z = C.z_contra_backtest(rets, self.retornos_bt(bot))
            if z < self.L["z_jubilacion"]:
                return True, (f"después de {len(rets)} operaciones, sus resultados están muy por debajo de lo que "
                              f"prometía el backtest (prueba estadística z = {z:.1f})")
        return False, ""

    def revisar(self):
        """Revisión diaria: jubilaciones, ascensos y lugares libres."""
        for bot in self.bots("titular") + self.bots("suplente"):
            jubilar, motivo = self.debe_jubilarse(bot)
            if jubilar:
                if bot["posicion"] is not None:
                    self._cerrar(bot, "jubilación")
                era = bot["rol"]
                bot["rol"], bot["motivo_jubilacion"] = "jubilado", motivo
                self.evento(f"👴 {bot['id']} ({_moneda(bot['simbolo'])} {bot['tf']}) se jubila ({era}): {motivo}.",
                            avisar=(era == "titular"))
        # Titulares que una y otra vez no llegan al mínimo de Binance: dejan su lugar a otro
        for tit in self.bots("titular"):
            if tit.get("omitidas_seguidas", 0) >= self.L.get("max_senales_sin_operar", 3) and tit["posicion"] is None:
                tit["rol"], tit["no_operable"] = "suplente", True
                self.evento(f"↩️ {tit['id']} ({_moneda(tit['simbolo'])}) vuelve a suplente: con {self.capital():.2f} USDT "
                            f"no llega al mínimo de Binance en sus operaciones. Dejo su lugar a otro bot.")
        minimo = self.L["min_operaciones_ascenso"]
        for tit in self.bots("titular"):
            if tit["posicion"] is not None or len(tit["trades"]) < minimo:
                continue
            rets_t = [t["retorno"] for t in tit["trades"]]
            mejor, mejor_t = None, self.L["t_minimo_ascenso"]
            for sup in self.bots("suplente"):
                if len(sup["trades"]) < minimo or not self.elegible(sup, excluir=tit["id"]):
                    continue
                t = C.t_welch([x["retorno"] for x in sup["trades"]], rets_t)
                if t >= mejor_t:
                    mejor, mejor_t = sup, t
            if mejor:
                tit["rol"] = "suplente"
                self.evento(f"🔄 {tit['id']} vuelve al banco de suplentes: {mejor['id']} fue claramente mejor "
                            f"en vivo (t = {mejor_t:.1f}, con {len(mejor['trades'])} operaciones).")
                self._ascender(mejor, "fue claramente mejor que el titular que reemplaza")
        self.completar_titulares()
        self.e["ultima_revision"] = self.hoy()
        self.guardar()

    # ------------------------------------------------------------------ día y frenos
    def tick(self):
        c = self.e["cuenta"]
        if c["dia"] != self.hoy():
            c.update(dia=self.hoy(), inicio_dia=c["equity"], pnl_hoy=0.0, racha_hoy=0, freno_dia="")
            self.guardar()

    def puede_operar(self) -> Optional[str]:
        """None si los titulares pueden abrir operaciones; si no, el motivo."""
        if self.e["apagado"]:
            return "apagado: " + self.e["motivo_apagado"]
        if self.e["pausado"]:
            return "pausado"
        if self.modo == "real" and not self.e["real_confirmado"]:
            return "modo real sin confirmar por Telegram"
        if self.e["cuenta"]["freno_dia"]:
            return "freno diario: " + self.e["cuenta"]["freno_dia"]
        radar = self.e.get("radar") or {}
        if radar.get("hasta", 0) > self.reloj():
            return "radar externo: " + radar.get("motivo", "")
        return None

    def _controlar_cuenta(self):
        c = self.e["cuenta"]
        if not c["freno_dia"]:
            motivo = C.freno_diario(c["pnl_hoy"], c["racha_hoy"], c["inicio_dia"],
                                    self.R["perdida_max_dia_pct"], self.R["perdidas_seguidas_max_dia"])
            if motivo:
                c["freno_dia"] = motivo
                self.evento(f"🧯 Freno diario: {motivo}. No abro más operaciones hasta mañana (las abiertas siguen con su stop).")
        if not self.e["apagado"] and C.freno_total(c["equity"], c["pico"], self.R["caida_max_desde_pico_pct"]):
            caida = (c["pico"] - c["equity"]) / c["pico"] * 100
            self.cerrar_todo("freno total")
            self.e.update(apagado=True, motivo_apagado=f"la cuenta cayó {caida:.1f}% desde su máximo")
            self.evento(f"🛑 FRENO TOTAL: la cuenta cayó {caida:.1f}% desde su máximo ({c['pico']:.2f} → "
                        f"{c['equity']:.2f} USDT). Cerré todo y me apagué. Para volver: /reanudar confirmo")

    # ------------------------------------------------------------------ velas
    def mercados(self) -> set:
        return {(b["simbolo"], b["tf"]) for b in self.bots() if b["rol"] in ("titular", "suplente")}

    def procesar_velas(self, simbolo: str, tf: str, velas: pd.DataFrame):
        """Llamar cuando cierra una vela nueva de (simbolo, tf). `velas` = historia de velas cerradas."""
        if velas.empty:
            return
        ultima_ts = int(velas["ts"].iloc[-1])
        fresca = self.reloj() * 1000 - (ultima_ts + tf_ms(tf)) <= tf_ms(tf)
        externos_cache = None
        for bot in [b for b in self.bots() if b["rol"] in ("titular", "suplente") and b["simbolo"] == simbolo and b["tf"] == tf]:
            nuevas = velas[velas["ts"] > bot["ultima_vela_ts"]] if bot["ultima_vela_ts"] else velas.tail(1)
            for vela in nuevas.to_dict("records"):
                self._gestionar(bot, vela)
                bot["ultima_vela_ts"] = int(vela["ts"])
            if not (len(nuevas) and fresca and bot["rol"] in ("titular", "suplente")):
                continue
            if bot["posicion"] is not None and not bot["estrategia"]["salidas"].get("salida_contraria"):
                continue
            externos = None
            if usa_externos(bot["estrategia"]):
                if externos_cache is None:
                    externos_cache = self._externos(simbolo, tf, velas)
                externos = externos_cache
            if bot["posicion"] is not None:
                # Salida por señal contraria (como en las pruebas: en esta vela ya no se abre otra operación)
                if senal_contraria(bot["estrategia"], velas, bot["posicion"]["lado"], externos):
                    self._cerrar(bot, "señal de salida", precio_simulado=float(velas["close"].iloc[-1]))
                continue
            lado, atr = senal_ultima_vela(bot["estrategia"], velas, externos)
            if lado:
                self._abrir(bot, lado, atr, velas.iloc[-1].to_dict(), distancia_rango(bot["estrategia"], velas, lado))
        self._controlar_cuenta()
        self.guardar()

    def _externos(self, simbolo, tf, velas) -> dict:
        """Datos de afuera del gráfico para las estrategias que los usan. Si fallan, esas estrategias no entran."""
        try:
            return self.mercado.externos_vivo(simbolo, tf, velas, int(self.reloj() * 1000))
        except Exception as e:  # noqa: BLE001
            self._aviso_unico("externos", f"⚠️ No pude leer los datos externos (funding / Bitcoin / Miedo y Codicia): {e}. "
                                          "Las estrategias que los usan no abren operaciones hasta que vuelvan.")
            return {}

    def _gestionar(self, bot, vela):
        pos = bot["posicion"]
        if pos is None:
            return
        if self.con_dinero(bot):
            if self.ejecutor.posicion(bot["simbolo"]) is None:  # lo cerró el stop o el take-profit del exchange
                salida, pnl = self.ejecutor.resultado_cierre(bot["simbolo"], pos)
                self._registrar(bot, salida, pnl, pnl / pos["riesgo_usdt"], self._motivo(pos, salida) + " (exchange)")
                return
        else:
            tocado = revisar_vela(pos, vela, self.slip_stop)
            if tocado:
                self._cerrar_simulado(bot, *tocado)
                return
        stop_antes = pos["stop"]
        if cierre_de_vela(pos, vela, bot["estrategia"]["salidas"].get("max_velas", 0)) == "tiempo":
            self._cerrar(bot, "tiempo", precio_simulado=vela["close"])
        elif self.con_dinero(bot) and pos["stop"] != stop_antes:
            errores = self.ejecutor.mover_stop(bot["simbolo"], pos["lado"], pos["cantidad"], pos["stop"], pos.get("tp"))
            if errores:
                self._aviso_unico(f"stop-{bot['id']}", f"⚠️ No pude mover el stop de {bot['id']}: {errores[0]}. "
                                                      "El software lo sigue vigilando.")

    @staticmethod
    def _motivo(pos, salida):
        if pos.get("tp") is not None and abs(salida - pos["tp"]) < abs(salida - pos["stop"]):
            return "take-profit"
        return "stop móvil" if pos.get("stop_movido") else "stop-loss"

    def _abrir(self, bot, lado, atr, vela, dist_rango=None):
        if bot["rol"] == "titular":
            bloqueo = self.puede_operar()
            if bloqueo:
                return
            precio = self.ejecutor.precio(bot["simbolo"]) if self.con_dinero(bot) else vela["close"]
            niv = niveles(bot["estrategia"]["salidas"], lado, precio, atr, dist_rango)
            if niv is None:
                return
            capital = self.capital()
            riesgo = capital * self.riesgo_frac
            abierto = sum(b["posicion"]["riesgo_usdt"] for b in self.bots("titular") if b["posicion"])
            if not C.riesgo_abierto_permitido(abierto, riesgo, capital, self.R["riesgo_total_max_pct"]):
                self._aviso_unico(f"riesgo-{bot['id']}", f"⏸ {bot['id']} tenía señal pero el riesgo abierto total llegaría "
                                                         f"a más de {self.R['riesgo_total_max_pct']}%: no entra.")
                return
            min_q, min_n = self.mercado.limites(bot["simbolo"])
            cantidad, motivo = C.tamano(riesgo, niv["dist"], precio, capital, self.R["apalancamiento_max"],
                                        lambda q: self.mercado.ajustar(bot["simbolo"], q), min_q, min_n)
            if not cantidad:
                bot["omitidas"] = bot.get("omitidas", 0) + 1
                bot["omitidas_seguidas"] = bot.get("omitidas_seguidas", 0) + 1
                self._aviso_unico(f"min-{bot['id']}", f"🚫 {bot['id']} ({_moneda(bot['simbolo'])}) tuvo señal pero no "
                                                      f"opera: {motivo}. Con {capital:.2f} USDT y 1% de riesgo no alcanza.")
                return
            if self.con_dinero(bot):
                entrada, cantidad = self.ejecutor.abrir(bot["simbolo"], lado, cantidad)
                niv = niveles(bot["estrategia"]["salidas"], lado, entrada, atr, dist_rango)
            else:
                entrada = precio * (1 + self.slippage * lado)
                niv = niveles(bot["estrategia"]["salidas"], lado, entrada, atr, dist_rango)
            riesgo_real = cantidad * niv["dist"]
        else:
            entrada = vela["close"] * (1 + self.slippage * lado)
            niv = niveles(bot["estrategia"]["salidas"], lado, entrada, atr, dist_rango)
            if niv is None:
                return
            cantidad, riesgo_real = None, float(self.R["capital_inicial"]) * self.riesgo_frac
        bot["omitidas_seguidas"] = 0
        bot["posicion"] = {"lado": lado, "entrada": entrada, "cantidad": cantidad, "riesgo_usdt": riesgo_real,
                           "abierta_ts": int(self.reloj() * 1000), "velas": 0,
                           "abierta": self.ahora().isoformat(timespec="seconds"), **niv}
        if bot["rol"] == "titular":
            if self.con_dinero(bot):
                errores = self.ejecutor.proteger(bot["simbolo"], lado, cantidad, niv["stop"], niv["tp"])
                if errores:
                    self.evento(f"⚠️ No se pudieron poner las órdenes de protección de {bot['id']}: {errores[0]}. "
                                f"El software vigila el stop cada {self.L['intervalo_vigilancia']} segundos.")
            self.evento(f"🚀 {bot['id']} {'COMPRA' if lado == 1 else 'VENDE EN CORTO'} {_moneda(bot['simbolo'])} "
                        f"a {entrada:.6g} ({cantidad:g} unidades). Si sale mal pierde ≈{riesgo_real:.2f} USDT "
                        f"(stop {niv['stop']:.6g}).")

    def _cerrar_simulado(self, bot, precio_bruto, motivo):
        res = resultado(bot["posicion"], precio_bruto, self.comision, self.slippage, self.riesgo_frac)
        self._registrar(bot, res["salida"], res["pnl_usdt"], res["r"], motivo)

    def _cerrar(self, bot, motivo, precio_simulado=None):
        pos = bot["posicion"]
        if pos is None:
            return
        if self.con_dinero(bot):
            salida, pnl = self.ejecutor.cerrar(bot["simbolo"], pos)
            self._registrar(bot, salida, pnl, pnl / pos["riesgo_usdt"], motivo)
        else:
            precio = precio_simulado if precio_simulado is not None else self.mercado.precio(bot["simbolo"])
            self._cerrar_simulado(bot, precio, motivo)

    def _registrar(self, bot, salida, pnl, r, motivo):
        pos = bot["posicion"]
        trade = {"fecha": self.ahora().isoformat(timespec="seconds"), "rol": bot["rol"], "lado": pos["lado"],
                 "entrada": pos["entrada"], "salida": salida, "cantidad": pos["cantidad"], "r": r,
                 "retorno": r * self.riesgo_frac, "pnl_usdt": pnl, "motivo": motivo}
        bot["trades"].append(trade)
        bot["posicion"] = None
        self._csv(bot, trade)
        if bot["rol"] == "titular":
            c = self.e["cuenta"]
            c["equity"] += pnl
            c["pico"] = max(c["pico"], c["equity"])
            c["pnl_hoy"] += pnl
            c["racha_hoy"] = c.get("racha_hoy", 0) + 1 if pnl < 0 else 0  # pérdidas seguidas en el día
            self.evento(f"{'✅' if pnl > 0 else '❌'} {bot['id']} cerró {_moneda(bot['simbolo'])}: "
                        f"{pnl:+.2f} USDT ({r:+.1f} veces lo arriesgado), por {motivo}. Cuenta: {c['equity']:.2f} USDT.")

    def _csv(self, bot, t):
        nuevo = not os.path.exists(self.ruta_csv)
        os.makedirs(self.carpeta, exist_ok=True)
        with open(self.ruta_csv, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS_CSV)
            if nuevo:
                w.writeheader()
            w.writerow({"fecha": t["fecha"], "bot": bot["id"], "rol": t["rol"],
                        "modo": self.modo if t["rol"] == "titular" else "papel", "simbolo": bot["simbolo"],
                        "tf": bot["tf"], "lado": "LONG" if t["lado"] == 1 else "SHORT", "entrada": round(t["entrada"], 8),
                        "salida": round(t["salida"], 8), "cantidad": t["cantidad"] or "", "r": round(t["r"], 3),
                        "pnl_usdt": round(t["pnl_usdt"], 4), "motivo": t["motivo"]})

    # ------------------------------------------------------------------ vigilancia y comandos
    def vigilar(self):
        """Cada 30 s: respaldo por software del stop/take-profit de los titulares con dinero."""
        for bot in self.bots("titular"):
            pos = bot["posicion"]
            if pos is None or not self.con_dinero(bot):
                continue
            if self.ejecutor.posicion(bot["simbolo"]) is None:
                salida, pnl = self.ejecutor.resultado_cierre(bot["simbolo"], pos)
                self._registrar(bot, salida, pnl, pnl / pos["riesgo_usdt"], self._motivo(pos, salida) + " (exchange)")
                continue
            precio = self.ejecutor.precio(bot["simbolo"])
            lado = pos["lado"]
            if (lado == 1 and precio <= pos["stop"]) or (lado == -1 and precio >= pos["stop"]):
                self._cerrar(bot, self._motivo(pos, pos["stop"]) + " (software)")
            elif pos.get("tp") is not None and ((lado == 1 and precio >= pos["tp"]) or (lado == -1 and precio <= pos["tp"])):
                self._cerrar(bot, "take-profit (software)")
        self._controlar_cuenta()
        self.guardar()

    def cerrar_todo(self, motivo="cierre manual"):
        for bot in self.bots("titular"):
            if bot["posicion"] is not None:
                self._cerrar(bot, motivo)
        self.guardar()

    # ------------------------------------------------------------------ textos para Telegram
    def _stats(self, bot, desde: Optional[str] = None):
        trades = [t for t in bot["trades"] if desde is None or t["fecha"] >= desde]
        n = len(trades)
        ganadas = sum(t["r"] > 0 for t in trades)
        return n, ganadas, sum(t["r"] for t in trades), sum(t["pnl_usdt"] for t in trades)

    def texto_estado(self) -> str:
        c = self.e["cuenta"]
        bloqueo = self.puede_operar()
        estado = "🟢 Prendido y operando" if not bloqueo else f"🟡 {bloqueo}" if not self.e["apagado"] else f"🔴 {bloqueo}"
        modo = {"papel": "simulado (sin Binance)", "testnet": "PRÁCTICA (Demo de Binance, plata de mentira)",
                "real": "REAL (plata de verdad)"}[self.modo]
        abiertas = [b for b in self.bots("titular") if b["posicion"]]
        lineas = [f"📊 {estado}", f"Modo: {modo}",
                  f"Cuenta: {c['equity']:.2f} USDT (máximo {c['pico']:.2f}) · hoy {c['pnl_hoy']:+.2f} USDT",
                  f"Titulares: {len(self.bots('titular'))} · suplentes: {len(self.bots('suplente'))} · "
                  f"jubilados: {len(self.bots('jubilado'))}"]
        if abiertas:
            lineas.append("Operaciones abiertas:")
            for b in abiertas:
                p = b["posicion"]
                lineas.append(f"  {b['id']} {'compra' if p['lado'] == 1 else 'venta'} {_moneda(b['simbolo'])} "
                              f"a {p['entrada']:.6g}, stop {p['stop']:.6g}")
        else:
            lineas.append("Sin operaciones abiertas.")
        return "\n".join(lineas)

    def texto_hoy(self) -> str:
        c = self.e["cuenta"]
        hoy = self.hoy()
        trades = [(b, t) for b in self.bots() for t in b["trades"] if t["fecha"].startswith(hoy) and t["rol"] == "titular"]
        if not trades:
            base = "Hoy todavía no se cerró ninguna operación."
        else:
            ganadas = sum(t["pnl_usdt"] > 0 for _, t in trades)
            base = (f"Hoy se cerraron {len(trades)} operaciones: {ganadas} ganaron y {len(trades) - ganadas} perdieron. "
                    f"Resultado: {c['pnl_hoy']:+.2f} USDT.")
        if c["freno_dia"]:
            base += f"\nEl freno diario está activo ({c['freno_dia']}): mañana se vuelve a operar."
        return f"📅 {base}\nLa cuenta tiene {c['equity']:.2f} USDT."

    def texto_bots(self) -> str:
        lineas = ["🏆 TITULARES"]
        for b in self.bots("titular") or []:
            n, g, r, pnl = self._stats(b)
            lineas.append(f"• {'🧪 ' if b.get('nivel') == 'exploracion' else ''}{b['id']} {_moneda(b['simbolo'])} {b['tf']}: {n} operaciones en vivo, {g} ganadas, "
                          f"{r:+.1f}R ({pnl:+.2f} USDT){' · abierta' if b['posicion'] else ''}")
        if not self.bots("titular"):
            lineas.append("(todavía ninguno)")
        lineas.append("🪑 SUPLENTES (practican simulados)")
        for b in sorted(self.bots("suplente"), key=lambda x: -sum(t["r"] for t in x["trades"]))[:10]:
            n, g, r, _ = self._stats(b)
            lineas.append(f"• {'🧪 ' if b.get('nivel') == 'exploracion' else ''}{b['id']} {_moneda(b['simbolo'])} {b['tf']}: {n} operaciones, {g} ganadas, {r:+.1f}R")
        if not self.bots("suplente"):
            lineas.append("(ninguno)")
        lineas.append("R = veces lo arriesgado (+2R = ganó el doble de lo que arriesgaba).")
        if any(b.get("nivel") == "exploracion" for b in self.bots()):
            lineas.append("🧪 = en prueba con filtros flojos: solo practica, nunca con plata real.")
        return "\n".join(lineas)

    def texto_noche(self) -> str:
        c = self.e["cuenta"]
        hoy = self.hoy()
        n = sum(1 for b in self.bots() for t in b["trades"] if t["fecha"].startswith(hoy) and t["rol"] == "titular")
        resultado_dia = "ganó" if c["pnl_hoy"] > 0 else "perdió" if c["pnl_hoy"] < 0 else "quedó igual"
        partes = [f"🌙 Resumen del día: la cuenta {resultado_dia} {abs(c['pnl_hoy']):.2f} dólares con {n} operaciones "
                  f"y ahora tiene {c['equity']:.2f}."]
        abiertas = sum(1 for b in self.bots("titular") if b["posicion"])
        partes.append(f"Hay {len(self.bots('titular'))} bots titulares trabajando y {abiertas} operación(es) abierta(s).")
        hechos = [e["texto"].split("\n")[0] for e in self.e["eventos"] if e["fecha"].startswith(hoy)
                  and e["texto"][:2] in ("⬆️", "👴", "🔄", "🧯", "🛑")]
        if hechos:
            partes.append("Novedades: " + " ".join(hechos[:2]))
        else:
            partes.append("Sin cambios en el equipo. Todo en orden." if not self.puede_operar() else f"Ojo: {self.puede_operar()}.")
        return "\n".join(partes)

    def texto_semana(self) -> str:
        desde = datetime.fromtimestamp(self.reloj() - 7 * 86400, tz=timezone.utc).isoformat(timespec="seconds")
        lineas = ["📰 INFORME SEMANAL"]
        total = 0.0
        for b in self.bots("titular") + self.bots("suplente"):
            n, g, r, pnl = self._stats(b, desde)
            if n:
                if b["rol"] == "titular":
                    total += pnl
                lineas.append(f"• {b['id']} ({b['rol']}, {_moneda(b['simbolo'])} {b['tf']}): {n} operaciones, "
                              f"{g} ganadas, {r:+.1f}R")
        lineas.insert(1, f"Resultado de los titulares en 7 días: {total:+.2f} USDT. Cuenta: {self.e['cuenta']['equity']:.2f} USDT.")
        hechos = [e["texto"].split("\n")[0] for e in self.e["eventos"] if e["fecha"] >= desde
                  and e["texto"][:2] in ("⬆️", "👴", "🔄", "🧯", "🛑", "🆕")]
        lineas.append("Cambios en la liga:" if hechos else "Sin cambios en la liga esta semana.")
        lineas += [f"  {h}" for h in hechos[-10:]]
        return "\n".join(lineas)
