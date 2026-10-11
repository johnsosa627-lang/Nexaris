"""Filtro IA vía OpenRouter, con presupuesto diario y semanal de llamadas."""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Callable, Optional, Tuple

import pandas as pd
import requests

log = logging.getLogger("trader")

URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"

PROMPT_SISTEMA = (
    "Sos un analista de trading de futuros de criptomonedas, prudente y escéptico. "
    "Recibís velas de 15 minutos (o el timeframe indicado) con indicadores técnicos y una "
    "señal técnica propuesta. Evaluá la probabilidad de que la operación propuesta alcance "
    "el take-profit antes que el stop-loss. Respondé ÚNICAMENTE con un JSON válido, sin texto "
    'extra, con este formato exacto: {"score": <entero 0-100>, "motivo": "<explicación breve en español>"}'
)


class ErrorIA(Exception):
    pass


def parsear_respuesta(texto: str) -> Tuple[int, str]:
    """Extrae {"score","motivo"} aunque el modelo agregue texto o bloques ```json."""
    if not texto:
        raise ErrorIA("Respuesta vacía de la IA")
    candidatos = [texto.strip()]
    candidatos += re.findall(r"\{.*?\}", texto, flags=re.DOTALL)
    candidatos += re.findall(r"\{.*\}", texto, flags=re.DOTALL)
    for candidato in candidatos:
        candidato = re.sub(r"^```(?:json)?|```$", "", candidato.strip()).strip()
        try:
            datos = json.loads(candidato)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(datos, dict) and "score" in datos:
            score = int(round(float(datos["score"])))
            if not 0 <= score <= 100:
                raise ErrorIA(f"Score fuera de rango: {score}")
            return score, str(datos.get("motivo", "")).strip()
    raise ErrorIA(f"No se pudo interpretar la respuesta: {texto[:200]}")


def tabla_velas(df: pd.DataFrame, n: int) -> str:
    columnas = ["ts", "open", "high", "low", "close", "volume", "ema9", "ema21", "rsi",
                "macd_hist", "bb_sup", "bb_inf", "vol_media"]
    ult = df[columnas].tail(n).copy()
    ult["ts"] = pd.to_datetime(ult["ts"], unit="ms", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    ult = ult.rename(columns={"ts": "fecha_utc"})
    return ult.to_csv(index=False, float_format="%.6g")


class FiltroIA:
    def __init__(self, cfg, estado, post: Callable = requests.post,
                 reloj: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.cfg = cfg
        self.estado = estado
        self.post = post
        self.reloj = reloj

    # ---------- presupuesto ----------
    def _contadores(self) -> dict:
        ahora = self.reloj()
        dia = ahora.date().isoformat()
        anio, semana, _ = ahora.isocalendar()
        clave_semana = f"{anio}-W{semana:02d}"
        ia = dict(self.estado["ia"])
        if ia.get("dia") != dia:
            ia["dia"], ia["llamadas_dia"] = dia, 0
        if ia.get("semana") != clave_semana:
            ia["semana"], ia["llamadas_semana"] = clave_semana, 0
        return ia

    def presupuesto_disponible(self) -> bool:
        ia = self._contadores()
        return ia["llamadas_dia"] < self.cfg.ia_max_dia and ia["llamadas_semana"] < self.cfg.ia_max_semana

    def uso(self) -> dict:
        ia = self._contadores()
        return {"dia": ia["llamadas_dia"], "max_dia": self.cfg.ia_max_dia,
                "semana": ia["llamadas_semana"], "max_semana": self.cfg.ia_max_semana}

    def _registrar_llamada(self):
        ia = self._contadores()
        ia["llamadas_dia"] += 1
        ia["llamadas_semana"] += 1
        self.estado["ia"] = ia

    # ---------- consulta ----------
    def _consultar_modelo(self, modelo: str, mensaje_usuario: str) -> Tuple[int, str]:
        self._registrar_llamada()
        respuesta = self.post(
            URL_OPENROUTER,
            headers={
                "Authorization": f"Bearer {self.cfg.openrouter_api_key}",
                "Content-Type": "application/json",
                "X-Title": "bot-futuros",
            },
            json={
                "model": modelo,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": PROMPT_SISTEMA},
                    {"role": "user", "content": mensaje_usuario},
                ],
            },
            timeout=self.cfg.ia_timeout,
        )
        if respuesta.status_code != 200:
            raise ErrorIA(f"HTTP {respuesta.status_code}: {respuesta.text[:200]}")
        datos = respuesta.json()
        if "error" in datos:
            raise ErrorIA(str(datos["error"])[:200])
        try:
            contenido = datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ErrorIA(f"Formato inesperado: {str(datos)[:200]}")
        return parsear_respuesta(contenido)

    def evaluar(self, df: pd.DataFrame, lado: str) -> Tuple[bool, Optional[int], str]:
        """Devuelve (aprobada, score, motivo). Cualquier falla => no aprobada."""
        if not self.cfg.openrouter_api_key:
            return False, None, "Falta OPENROUTER_API_KEY"
        mensaje = (
            f"Par: {self.cfg.simbolo} | Timeframe: {self.cfg.timeframe}\n"
            f"Señal técnica propuesta: {lado}\n"
            f"Stop-loss: {self.cfg.stop_loss_pct}% | Take-profit: {self.cfg.take_profit_pct}% | "
            f"Apalancamiento: {self.cfg.apalancamiento}x\n"
            f"Últimas {self.cfg.ia_velas} velas cerradas (la última es la de la señal):\n"
            f"{tabla_velas(df, self.cfg.ia_velas)}\n"
            'Respondé solo el JSON {"score": 0-100, "motivo": "..."}.'
        )
        errores = []
        for modelo in (self.cfg.ia_modelo, self.cfg.ia_modelo_respaldo):
            if not modelo:
                continue
            if not self.presupuesto_disponible():
                errores.append("presupuesto de IA agotado")
                break
            try:
                score, motivo = self._consultar_modelo(modelo, mensaje)
                log.info("IA %s -> score %s | %s", modelo, score, motivo)
                return score >= self.cfg.ia_score_minimo, score, f"[{modelo}] {motivo}"
            except Exception as e:  # noqa: BLE001 - cualquier falla de la IA bloquea la operación
                log.warning("Falla IA con %s: %s", modelo, e)
                errores.append(f"{modelo}: {e}")
        return False, None, "IA no disponible -> " + " | ".join(errores)
