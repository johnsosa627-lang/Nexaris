"""Núcleo del bot: ciclo de vigilancia, entradas, cierres y protecciones."""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from . import riesgo
from .estrategia import evaluar_senal, timeframe_a_ms, velas_cerradas
from .indicadores import agregar_indicadores, ohlcv_a_dataframe

log = logging.getLogger("trader")


def fmt(valor: float, decimales: int = 4) -> str:
    return f"{valor:,.{decimales}f}"


class Bot:
    def __init__(self, cfg, broker, estado, ia, registro, notificar: Callable[[str], None],
                 reloj: Callable[[], float] = time.time):
        self.cfg = cfg
        self.broker = broker
        self.estado = estado
        self.ia = ia
        self.registro = registro
        self.notificar = notificar
        self.reloj = reloj
        self.lock = threading.RLock()
        self._ultimo_error = ("", 0.0)

    # ------------------------------------------------------------------ utilidades
    def ahora(self) -> datetime:
        return datetime.fromtimestamp(self.reloj(), tz=timezone.utc)

    def hoy(self) -> str:
        return self.ahora().date().isoformat()

    def _apagar(self, motivo: str):
        self.estado.actualizar(apagado=True, motivo_apagado=motivo)
        log.error("BOT APAGADO: %s", motivo)
        self.notificar(f"🛑 BOT APAGADO\n{motivo}\nUsá /estado para ver la situación y /reactivar cuando corresponda.")

    def avisar_error(self, texto: str):
        """Notifica errores sin inundar Telegram (mismo error a lo sumo cada 10 min)."""
        ultimo, cuando = self._ultimo_error
        if texto != ultimo or self.reloj() - cuando > 600:
            self.notificar(f"⚠️ Error: {texto}")
            self._ultimo_error = (texto, self.reloj())

    # ------------------------------------------------------------------ arranque
    def iniciar(self):
        with self.lock:
            if self.cfg.modo == "real" and not self.cfg.confirmar_real:
                self._apagar("MODO=real requiere CONFIRMAR_REAL=SI. No se opera.")
                return
            if self.cfg.modo == "real" and self.estado["motivo_apagado"].startswith("MODO=real"):
                self.estado.actualizar(apagado=False, motivo_apagado="")
            self.broker.cargar_mercado()
            self.broker.preparar()
            self._control_dia(self.broker.saldo())
            self.sincronizar_posicion()
            saldo = self.broker.saldo()
            estado_txt = "APAGADO (" + self.estado["motivo_apagado"] + ")" if self.estado["apagado"] else (
                "PAUSADO" if self.estado["pausado"] else "activo")
            self.notificar(
                f"🤖 Bot iniciado\nModo: {self.cfg.modo.upper()} | {self.cfg.simbolo} {self.cfg.timeframe}\n"
                f"Saldo: {fmt(saldo)} USDT | Apalancamiento: {self.cfg.apalancamiento}x aislado\n"
                f"SL {self.cfg.stop_loss_pct}% / TP {self.cfg.take_profit_pct}% | Estado: {estado_txt}")

    def sincronizar_posicion(self):
        """Al reiniciar, toma como verdad lo que hay en el exchange para no duplicar."""
        pos_bot = self.estado["posicion"]
        pos_ex = self.broker.posicion()
        if pos_ex and pos_bot and pos_ex["lado"] == pos_bot["lado"]:
            pos_bot = {**pos_bot, "cantidad": pos_ex["cantidad"]}
            self.estado["posicion"] = pos_bot
            self._reponer_protecciones(pos_bot)
            self.notificar(f"♻️ Posición {pos_bot['lado']} recuperada tras reinicio "
                           f"(entrada {fmt(pos_bot['entrada'])}, SL {fmt(pos_bot['sl'])}, TP {fmt(pos_bot['tp'])}).")
        elif pos_ex:
            sl, tp = riesgo.calcular_niveles(pos_ex["lado"], pos_ex["entrada"],
                                             self.cfg.stop_loss_pct, self.cfg.take_profit_pct)
            pos = {**pos_ex, "sl": sl, "tp": tp, "abierta_ts": int(self.reloj() * 1000),
                   "abierta_iso": self.ahora().isoformat(timespec="seconds"), "adoptada": True}
            self.estado["posicion"] = pos
            self._reponer_protecciones(pos)
            self.notificar(f"♻️ Encontré una posición {pos['lado']} abierta en el exchange "
                           f"({pos['cantidad']} a {fmt(pos['entrada'])}). La adopto con SL {fmt(sl)} y TP {fmt(tp)}.")
        elif pos_bot:
            log.info("La posición guardada ya no existe en el exchange: se cerró mientras el bot estaba apagado")
            salida, pnl = self.broker.cierre_externo(pos_bot)
            self._registrar_cierre(pos_bot, salida, pnl, "cerrada mientras el bot estaba apagado")

    def _reponer_protecciones(self, pos: dict):
        self.broker.cancelar_protecciones()
        errores = self.broker.colocar_protecciones(pos["lado"], pos["cantidad"], pos["sl"], pos["tp"])
        if errores:
            self.notificar("⚠️ No se pudieron colocar SL/TP en el exchange (el software los vigila igual):\n"
                           + "\n".join(errores))

    # ------------------------------------------------------------------ ciclo
    def _control_dia(self, saldo: float):
        dia = self.hoy()
        if self.estado["dia"] != dia:
            self.estado.actualizar(dia=dia, saldo_inicio_dia=saldo, operaciones_hoy=0)
            log.info("Nuevo día UTC %s. Saldo de inicio: %.4f", dia, saldo)
        elif self.estado["saldo_inicio_dia"] is None:
            self.estado["saldo_inicio_dia"] = saldo

    def corte_activo(self) -> bool:
        return self.estado["corte_dia"] == self.hoy()

    def ciclo(self):
        """Se ejecuta cada INTERVALO_VIGILANCIA segundos."""
        with self.lock:
            if self.estado["apagado"]:
                return
            saldo = self.broker.saldo()
            self._control_dia(saldo)
            if self.estado["posicion"]:
                self.vigilar_posicion()
            if self.estado["apagado"]:
                return
            if not self.estado["posicion"] and self.broker.modo != "papel" and self.broker.posicion():
                self.sincronizar_posicion()  # posición sin registrar (ej. apertura interrumpida): adoptarla
            if not self.estado["posicion"]:
                saldo = self.broker.saldo()
                if saldo < self.cfg.saldo_minimo:
                    self._apagar(f"Saldo {fmt(saldo)} USDT por debajo del mínimo de {fmt(self.cfg.saldo_minimo, 2)} USDT.")
                    return
                self._verificar_corte(saldo)
            self.evaluar_entrada()

    def _verificar_corte(self, saldo: float):
        if self.corte_activo():
            return
        if riesgo.corte_diario_alcanzado(self.estado["saldo_inicio_dia"], saldo, self.cfg.perdida_max_dia_pct):
            self.estado["corte_dia"] = self.hoy()
            perdida = self.estado["saldo_inicio_dia"] - saldo
            self.notificar(f"🧯 CORTE DE SEGURIDAD: pérdida del día {fmt(perdida)} USDT "
                           f"(≥ {self.cfg.perdida_max_dia_pct}%). No opero hasta mañana (UTC).")

    # ------------------------------------------------------------------ posición abierta
    def vigilar_posicion(self):
        pos = self.estado["posicion"]
        if self.broker.modo != "papel" and self.broker.posicion() is None:
            salida, pnl = self.broker.cierre_externo(pos)
            motivo = self._motivo_por_precio(pos, salida, pnl, sufijo=" (orden del exchange)")
            self._registrar_cierre(pos, salida, pnl, motivo)
            return
        precio = self.broker.precio()
        tocado = riesgo.tocado_sl_tp(pos["lado"], precio, pos["sl"], pos["tp"])
        if tocado:
            log.info("Precio %.6f tocó %s: cierre por software", precio, tocado)
            self.cerrar_posicion(f"{'stop-loss' if tocado == 'SL' else 'take-profit'} (software)")

    @staticmethod
    def _motivo_por_precio(pos, salida, pnl, sufijo=""):
        cerca_tp = abs(salida - pos["tp"]) < abs(salida - pos["sl"])
        if cerca_tp and pnl > 0:
            return "take-profit" + sufijo
        if not cerca_tp and pnl < 0:
            return "stop-loss" + sufijo
        return "cierre externo" + sufijo

    def cerrar_posicion(self, motivo: str) -> str:
        with self.lock:
            pos = self.estado["posicion"]
            if not pos:
                return "No hay posición abierta."
            salida, pnl = self.broker.cerrar(pos)
            self._registrar_cierre(pos, salida, pnl, motivo)
            return ""

    def _registrar_cierre(self, pos: dict, salida: float, pnl: float, motivo: str):
        self.registro.guardar({
            "fecha": self.ahora().isoformat(timespec="seconds"),
            "fecha_apertura": pos.get("abierta_iso", ""),
            "modo": self.cfg.modo,
            "simbolo": self.cfg.simbolo,
            "lado": pos["lado"],
            "entrada": round(pos["entrada"], 8),
            "salida": round(salida, 8),
            "cantidad": pos["cantidad"],
            "resultado_usdt": round(pnl, 6),
            "motivo_cierre": motivo,
        })
        self.estado["posicion"] = None
        saldo = self.broker.saldo()
        icono = "✅" if pnl > 0 else "❌"
        self.notificar(f"{icono} CIERRE {pos['lado']} {self.cfg.simbolo}\n"
                       f"Entrada {fmt(pos['entrada'])} → Salida {fmt(salida)}\n"
                       f"Resultado: {pnl:+.4f} USDT | Motivo: {motivo}\nSaldo: {fmt(saldo)} USDT")
        self._verificar_corte(saldo)
        if saldo < self.cfg.saldo_minimo:
            self._apagar(f"Saldo {fmt(saldo)} USDT por debajo del mínimo de {fmt(self.cfg.saldo_minimo, 2)} USDT.")

    # ------------------------------------------------------------------ entradas
    def evaluar_entrada(self):
        velas = self.broker.velas(250)
        df = velas_cerradas(ohlcv_a_dataframe(velas), self.cfg.timeframe, int(self.reloj() * 1000))
        if len(df) < 60:
            return
        ts_vela = int(df["ts"].iloc[-1])
        if ts_vela <= int(self.estado["ultima_vela_ts"] or 0):
            return  # esta vela ya se evaluó
        self.estado["ultima_vela_ts"] = ts_vela
        if self.estado["pausado"] or self.estado["posicion"] or self.corte_activo():
            return
        if self.estado["operaciones_hoy"] >= self.cfg.max_operaciones_dia:
            return
        # Margen: la vela recién cerrada no debe ser vieja (p.ej. tras una caída de datos)
        if self.reloj() * 1000 - (ts_vela + timeframe_a_ms(self.cfg.timeframe)) > timeframe_a_ms(self.cfg.timeframe):
            return
        df = agregar_indicadores(df)
        lado = evaluar_senal(df)
        if not lado:
            return
        log.info("Señal técnica %s en vela %s", lado, ts_vela)
        self.abrir_posicion(lado, df)

    def abrir_posicion(self, lado: str, df):
        if self.broker.posicion():
            log.warning("Ya hay una posición en el exchange: no abro otra")
            return
        precio = self.broker.precio()
        saldo = self.broker.saldo()
        cantidad = self.broker.ajustar_cantidad(
            riesgo.calcular_cantidad(saldo, self.cfg.fraccion_margen, self.cfg.apalancamiento, precio))
        ok, detalle = riesgo.validar_minimos(cantidad, precio, self.broker.min_cantidad, self.broker.min_nocional)
        if not ok:
            self.notificar(f"🚫 Señal {lado} sin operar: no alcanza el mínimo del par.\n{detalle}\n"
                           f"Saldo {fmt(saldo)} USDT, precio {fmt(precio)}.")
            return
        if not self.ia.presupuesto_disponible():
            uso = self.ia.uso()
            self.notificar(f"🚫 Señal {lado} sin operar: presupuesto de IA agotado "
                           f"({uso['dia']}/{uso['max_dia']} hoy, {uso['semana']}/{uso['max_semana']} semana).")
            return
        aprobada, score, motivo = self.ia.evaluar(df, lado)
        if score is None:
            self.notificar(f"🚫 Señal {lado} sin operar: la IA falló.\n{motivo}")
            return
        if not aprobada:
            self.notificar(f"🤔 Señal {lado} descartada por la IA (score {score} < {self.cfg.ia_score_minimo}).\n{motivo}")
            return

        abierta_ts = int(self.reloj() * 1000)
        entrada, cantidad = self.broker.abrir(lado, cantidad)
        sl, tp = riesgo.calcular_niveles(lado, entrada, self.cfg.stop_loss_pct, self.cfg.take_profit_pct)
        pos = {"lado": lado, "cantidad": cantidad, "entrada": entrada, "sl": sl, "tp": tp,
               "abierta_ts": abierta_ts, "abierta_iso": self.ahora().isoformat(timespec="seconds"),
               "score_ia": score}
        self.estado.actualizar(posicion=pos, operaciones_hoy=self.estado["operaciones_hoy"] + 1)
        errores = self.broker.colocar_protecciones(lado, cantidad, sl, tp)
        margen = entrada * cantidad / self.cfg.apalancamiento
        self.notificar(
            f"🚀 APERTURA {lado} {self.cfg.simbolo}\nEntrada {fmt(entrada)} | Cantidad {cantidad}\n"
            f"Margen ≈ {fmt(margen, 2)} USDT x{self.cfg.apalancamiento}\nSL {fmt(sl)} | TP {fmt(tp)}\n"
            f"IA score {score}: {motivo[:300]}\nOperación {self.estado['operaciones_hoy']}/{self.cfg.max_operaciones_dia} del día")
        if errores:
            self.notificar("⚠️ SL/TP no quedaron en el exchange; el software los vigila cada "
                           f"{self.cfg.intervalo_vigilancia}s.\n" + "\n".join(errores))

    # ------------------------------------------------------------------ comandos Telegram
    def cmd_estado(self) -> str:
        with self.lock:
            try:
                saldo = self.broker.saldo()
            except Exception as e:  # noqa: BLE001
                return f"⚠️ No pude leer el saldo: {e}"
            resumen = self.registro.resumen(self.cfg.modo, self.hoy())
            if self.estado["apagado"]:
                situacion = f"🛑 APAGADO: {self.estado['motivo_apagado']}"
            elif self.corte_activo():
                situacion = "🧯 Corte diario activo (vuelve mañana UTC)"
            elif self.estado["pausado"]:
                situacion = "⏸ Pausado"
            else:
                situacion = "▶️ Activo"
            pos = self.estado["posicion"]
            if pos:
                try:
                    precio = self.broker.precio()
                    flotante = riesgo.calcular_pnl(pos["lado"], pos["entrada"], precio, pos["cantidad"], 0)
                    extra = f"\n   Precio {fmt(precio)} | Flotante {flotante:+.4f} USDT"
                except Exception:  # noqa: BLE001
                    extra = ""
                txt_pos = (f"{pos['lado']} {pos['cantidad']} @ {fmt(pos['entrada'])}\n"
                           f"   SL {fmt(pos['sl'])} | TP {fmt(pos['tp'])}{extra}")
            else:
                txt_pos = "ninguna"
            uso = self.ia.uso()
            inicio = self.estado["saldo_inicio_dia"] or saldo
            return (
                f"📊 ESTADO — modo {self.cfg.modo.upper()}\n{situacion}\n"
                f"Par: {self.cfg.simbolo} {self.cfg.timeframe}\n"
                f"Saldo: {fmt(saldo)} USDT (inicio del día {fmt(inicio)})\n"
                f"Posición: {txt_pos}\n"
                f"Hoy: {resumen['hoy']:+.4f} USDT en {resumen['operaciones_hoy']} cierres | "
                f"aperturas {self.estado['operaciones_hoy']}/{self.cfg.max_operaciones_dia}\n"
                f"Total: {resumen['total']:+.4f} USDT en {resumen['operaciones_total']} operaciones "
                f"({resumen['ganadas']} ganadas)\n"
                f"IA: {uso['dia']}/{uso['max_dia']} hoy, {uso['semana']}/{uso['max_semana']} semana")

    def cmd_pausar(self) -> str:
        self.estado["pausado"] = True
        return "⏸ Bot pausado: no abre nuevas operaciones. La posición abierta (si hay) sigue vigilada."

    def cmd_reanudar(self) -> str:
        self.estado["pausado"] = False
        return "▶️ Bot reanudado."

    def cmd_cerrar(self) -> str:
        if not self.estado["posicion"]:
            return "No hay posición abierta."
        return self.cerrar_posicion("cierre manual (/cerrar)") or ""

    def cmd_operaciones(self) -> str:
        filas = self.registro.ultimas(10, self.cfg.modo)
        if not filas:
            return "Todavía no hay operaciones registradas."
        lineas = ["🧾 Últimas operaciones:"]
        for f in reversed(filas):
            r = float(f["resultado_usdt"])
            lineas.append(f"{'✅' if r > 0 else '❌'} {f['fecha'][:16].replace('T', ' ')} {f['lado']} "
                          f"{float(f['entrada']):.4f}→{float(f['salida']):.4f} {r:+.4f} USDT ({f['motivo_cierre']})")
        return "\n".join(lineas)

    def cmd_reactivar(self) -> str:
        with self.lock:
            if not self.estado["apagado"]:
                return "El bot no está apagado."
            if self.cfg.modo == "real" and not self.cfg.confirmar_real:
                return "No se puede: MODO=real sin CONFIRMAR_REAL=SI."
            saldo = self.broker.saldo()
            if saldo < self.cfg.saldo_minimo:
                return f"No se puede reactivar: saldo {fmt(saldo)} USDT < mínimo {fmt(self.cfg.saldo_minimo, 2)}."
            self.estado.actualizar(apagado=False, motivo_apagado="", saldo_inicio_dia=saldo)
            return f"✅ Bot reactivado con saldo {fmt(saldo)} USDT."

    def cmd_ayuda(self) -> str:
        return ("Comandos:\n/estado — modo, saldo, posición y resultados\n/pausar — no abre nuevas operaciones\n"
                "/reanudar — vuelve a operar\n/cerrar — cierra la posición a mercado\n"
                "/operaciones — últimas 10 operaciones\n/reactivar — reactiva tras un apagado (si el saldo alcanza)")
