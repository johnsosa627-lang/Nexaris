"""Radar externo: mira lo que pasa FUERA del gráfico y protege a los bots.

No intenta adivinar hacia dónde va el precio (operar por noticias no tiene una ventaja comprobada).
Sirve para NO entrar en medio del caos:
- Datos económicos fuertes de EE.UU. (inflación, tasas de la Fed, empleo): pausa entradas nuevas
  un rato antes y después, y avisa con anticipación.
- Movimiento brusco de Bitcoin (arrastra a todo el mercado): pausa entradas nuevas un rato.
- Noticias graves de cripto (hackeos, quiebras, retiros frenados): avisa y pausa entradas nuevas.
- Otras noticias importantes (SEC, ETF, Fed, regulación) y el índice de Miedo y Codicia: solo avisa.

Las operaciones abiertas no se tocan: siguen protegidas por su stop-loss.
"""
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

log = logging.getLogger("fabrica")

URL_CALENDARIO = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
URL_MIEDO_CODICIA = "https://api.alternative.me/fng/?limit=1"


class Radar:
    def __init__(self, cfg: dict, estado: dict, mercado, enviar: Callable[[str], None],
                 reloj: Callable[[], float] = time.time, http_get: Callable = requests.get):
        self.C = cfg["radar"]
        self.e = estado.setdefault("radar", {})  # se guarda dentro del estado de la liga
        self.e.setdefault("hasta", 0)
        self.e.setdefault("motivo", "")
        self.e.setdefault("avisados", [])
        self.mercado = mercado
        self.enviar = enviar
        self.reloj = reloj
        self.get = http_get
        self._cache = {}

    # ------------------------------------------------------------------ utilidades
    def bloqueo(self) -> Optional[str]:
        """Motivo por el que el radar pausa las entradas nuevas, o None."""
        if self.e["hasta"] > self.reloj():
            falta = int((self.e["hasta"] - self.reloj()) / 60) + 1
            return f"radar externo: {self.e['motivo']} (unos {falta} min más)"
        return None

    def _pausar(self, minutos: float, motivo: str, hasta: Optional[float] = None):
        hasta = hasta or self.reloj() + minutos * 60
        if hasta > self.e["hasta"]:
            self.e["hasta"], self.e["motivo"] = hasta, motivo

    def _avisar_una_vez(self, clave: str, texto: str):
        if clave in self.e["avisados"]:
            return
        self.e["avisados"] = (self.e["avisados"] + [clave])[-500:]
        self.enviar(texto)

    def _bajar(self, url: str, cada_seg: int):
        """Descarga con memoria: no repite el pedido antes de `cada_seg` segundos."""
        guardado = self._cache.get(url)
        if guardado and self.reloj() - guardado[0] < cada_seg:
            return guardado[1]
        r = self.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (fabrica-radar)"})
        r.raise_for_status()
        self._cache[url] = (self.reloj(), r.text)
        return r.text

    # ------------------------------------------------------------------ revisión
    def revisar(self):
        for nombre, paso in (("calendario", self._calendario), ("bitcoin", self._volatilidad),
                             ("noticias", self._noticias), ("miedo", self._miedo_codicia)):
            if not self.C.get(nombre, True):
                continue
            try:
                paso()
            except Exception as e:  # noqa: BLE001 - una fuente caída no frena al resto
                log.warning("Radar (%s): %s", nombre, e)

    def _calendario(self):
        eventos = json.loads(self._bajar(URL_CALENDARIO, 6 * 3600))
        ahora = self.reloj()
        for ev in eventos:
            if ev.get("impact") != "High" or ev.get("country") != "USD":
                continue
            try:
                cuando = datetime.fromisoformat(ev["date"]).timestamp()
            except (KeyError, ValueError):
                continue
            titulo = ev.get("title", "dato económico")
            desde = cuando - self.C["minutos_antes"] * 60
            hasta = cuando + self.C["minutos_despues"] * 60
            clave = f"cal-{titulo}-{int(cuando)}"
            if cuando - self.C["aviso_previo_min"] * 60 <= ahora < desde:
                hora = datetime.fromtimestamp(cuando, tz=timezone.utc).strftime("%H:%M UTC")
                self._avisar_una_vez(clave + "-previo",
                                     f"📅 A las {hora} sale un dato económico fuerte de EE.UU.: «{titulo}». "
                                     f"Suele mover mucho el precio, así que pauso las entradas nuevas desde "
                                     f"{self.C['minutos_antes']} min antes hasta {self.C['minutos_despues']} min después.")
            if desde <= ahora < hasta:
                self._pausar(0, f"dato económico de EE.UU. «{titulo}»", hasta=hasta)
                self._avisar_una_vez(clave + "-pausa", f"⏸ Pausa por el dato «{titulo}». Las operaciones abiertas siguen con su stop.")

    def _volatilidad(self):
        ventana = self.C["volatilidad_ventana_min"]
        velas = self.mercado.velas("BTC/USDT:USDT", "5m", ventana // 5 + 2, int(self.reloj() * 1000))
        if len(velas) < 2:
            return
        ultimas = velas.tail(ventana // 5)
        desde, hasta = float(ultimas["open"].iloc[0]), float(ultimas["close"].iloc[-1])
        maximo, minimo = float(ultimas["high"].max()), float(ultimas["low"].min())
        cambio = (hasta - desde) / desde * 100
        rango = (maximo - minimo) / desde * 100
        if abs(cambio) >= self.C["volatilidad_btc_pct"] or rango >= self.C["volatilidad_btc_pct"] * 1.5:
            self._pausar(self.C["pausa_volatilidad_min"], f"Bitcoin se movió {cambio:+.1f}% en {ventana} min")
            bloque = int(self.reloj() // (self.C["pausa_volatilidad_min"] * 60))
            self._avisar_una_vez(f"btc-{bloque}",
                                 f"🌪 Bitcoin se movió {cambio:+.1f}% en {ventana} minutos (rango {rango:.1f}%). "
                                 f"Cuando BTC se mueve así arrastra a todo el mercado: pauso las entradas nuevas "
                                 f"{self.C['pausa_volatilidad_min']} min.")

    def _noticias(self):
        graves = [p.lower() for p in self.C["palabras_graves"]]
        importantes = [p.lower() for p in self.C["palabras_importantes"]]
        for url in self.C["fuentes_noticias"]:
            for titulo, enlace, fecha in leer_rss(self._bajar(url, 10 * 60)):
                if fecha and self.reloj() - fecha > 3 * 3600:
                    continue  # solo noticias de las últimas 3 horas
                texto = titulo.lower()
                if any(_contiene(texto, p) for p in graves) and self._afecta_mercado(texto):
                    self._pausar(self.C["pausa_noticia_grave_min"], f"noticia grave: {titulo[:80]}")
                    self._avisar_una_vez(f"news-{enlace}", f"🚨 Noticia grave: {titulo}\n{enlace}\n"
                                         f"Pauso las entradas nuevas {self.C['pausa_noticia_grave_min']} min por precaución.")
                elif any(_contiene(texto, p) for p in graves):
                    self._avisar_una_vez(f"news-{enlace}", f"📰 Noticia: {titulo}\n{enlace}\n(Es un caso puntual que no "
                                                           "mueve a todo el mercado: solo aviso, no pauso nada.)")
                elif any(_contiene(texto, p) for p in importantes):
                    self._avisar_una_vez(f"news-{enlace}", f"📰 Noticia importante: {titulo}\n{enlace}\n(Solo aviso, no cambia nada.)")

    def _afecta_mercado(self, texto: str) -> bool:
        """¿La noticia grave toca algo grande (exchange, stablecoin, red) o mucha plata? Si no, no se pausa."""
        if any(_contiene(texto, p.lower()) for p in self.C.get("afecta_mercado", [])):
            return True
        minimo = float(self.C.get("monto_grave_millones", 100))
        for numero, unidad in re.findall(r"\$\s?(\d+(?:[.,]\d+)?)\s*(billion|bn|b|million|mn|m)\b", texto):
            millones = float(numero.replace(",", ".")) * (1000 if unidad.startswith("b") else 1)
            if millones >= minimo:
                return True
        return not self.C.get("afecta_mercado")  # sin lista configurada: como antes, toda noticia grave pausa

    def _miedo_codicia(self):
        datos = json.loads(self._bajar(URL_MIEDO_CODICIA, 3600))["data"][0]
        valor = int(datos["value"])
        self.e["miedo_codicia"] = valor
        dia = datetime.fromtimestamp(self.reloj(), tz=timezone.utc).date().isoformat()
        if valor <= self.C["miedo_extremo"]:
            self._avisar_una_vez(f"fng-{dia}", f"😱 El mercado está en MIEDO EXTREMO ({valor}/100). Suele haber movimientos "
                                               "bruscos. Los bots siguen con sus reglas y sus stops.")
        elif valor >= self.C["codicia_extrema"]:
            self._avisar_una_vez(f"fng-{dia}", f"🤑 El mercado está en CODICIA EXTREMA ({valor}/100). Suele haber caídas "
                                               "bruscas después. Los bots siguen con sus reglas y sus stops.")

    def texto(self) -> str:
        lineas = ["🛰 RADAR EXTERNO"]
        b = self.bloqueo()
        lineas.append(f"⏸ Entradas nuevas en pausa: {b}" if b else "✅ Sin alertas: los bots pueden operar normal.")
        if "miedo_codicia" in self.e:
            v = self.e["miedo_codicia"]
            animo = "miedo extremo" if v <= 25 else "miedo" if v < 45 else "neutral" if v <= 55 else "codicia" if v < 75 else "codicia extrema"
            lineas.append(f"Ánimo del mercado (Miedo y Codicia): {v}/100, {animo}.")
        lineas.append("Vigila: datos económicos de EE.UU., movimientos bruscos de Bitcoin y noticias graves de cripto.")
        return "\n".join(lineas)


def _contiene(texto: str, palabra: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(palabra) + r"(?![a-z])", texto) is not None


def leer_rss(xml: str) -> list:
    """[(título, enlace, fecha_timestamp | None)] de un feed RSS o Atom."""
    from email.utils import parsedate_to_datetime
    raiz = ET.fromstring(xml)
    items = []
    for it in raiz.iter():
        etiqueta = it.tag.split("}")[-1]
        if etiqueta not in ("item", "entry"):
            continue
        hijos = {h.tag.split("}")[-1]: h for h in it}
        titulo = (hijos.get("title").text or "").strip() if hijos.get("title") is not None else ""
        enlace_el = hijos.get("link")
        enlace = ""
        if enlace_el is not None:
            enlace = (enlace_el.text or enlace_el.get("href") or "").strip()
        fecha = None
        for k in ("pubDate", "published", "updated"):
            if hijos.get(k) is not None and hijos[k].text:
                try:
                    fecha = parsedate_to_datetime(hijos[k].text).timestamp()
                except (TypeError, ValueError):
                    try:
                        fecha = datetime.fromisoformat(hijos[k].text.replace("Z", "+00:00")).timestamp()
                    except ValueError:
                        fecha = None
                break
        if titulo:
            items.append((titulo, enlace, fecha))
    return items
