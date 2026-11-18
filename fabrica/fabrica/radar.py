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
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

log = logging.getLogger("fabrica")

URL_CALENDARIO = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
URL_MIEDO_CODICIA = "https://api.alternative.me/fng/?limit=1"


PLAZOS_HORAS = (1, 4, 24)
MAX_REGISTRO = 3000   # ~1 MB como mucho: unos años de noticias


class Radar:
    def __init__(self, cfg: dict, estado: dict, mercado, enviar: Callable[[str], None],
                 reloj: Callable[[], float] = time.time, http_get: Callable = requests.get,
                 carpeta: Optional[str] = None):
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
        # Registro de noticias: qué pasó con el precio de Bitcoin 1, 4 y 24 horas después de cada una.
        # Solo anota (no cambia cómo se opera): sirve para ver más adelante si hay un patrón que valga la pena.
        self.ruta_registro = os.path.join(carpeta, "noticias.json") if carpeta else None
        self.registro = []
        if self.ruta_registro and os.path.exists(self.ruta_registro):
            try:
                with open(self.ruta_registro, encoding="utf-8") as f:
                    self.registro = json.load(f)
            except (OSError, ValueError):
                self.registro = []

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

    # ------------------------------------------------------------------ registro de noticias
    def _precio_btc(self) -> Optional[float]:
        try:
            return float(self.mercado.precio("BTC/USDT:USDT"))
        except Exception:  # noqa: BLE001 - sin precio no se anota nada
            return None

    def _anotar(self, clave: str, tipo: str, titulo: str):
        """Anota una noticia (una sola vez) con el precio de Bitcoin en ese momento."""
        if self.ruta_registro is None or any(r["clave"] == clave for r in self.registro[-500:]):
            return
        precio = self._precio_btc()
        if precio is None:
            return
        self.registro.append({"clave": clave, "ts": int(self.reloj()), "tipo": tipo, "titulo": titulo[:160],
                              "btc": precio})
        self.registro = self.registro[-MAX_REGISTRO:]
        self._guardar_registro()

    def _seguimiento(self):
        """Completa cuánto se movió Bitcoin 1, 4 y 24 horas después de cada noticia anotada."""
        if not self.registro:
            return
        ahora, cambio, precio = self.reloj(), False, None
        for r in self.registro:
            for horas in PLAZOS_HORAS:
                campo = f"mov_{horas}h"
                if campo in r or ahora - r["ts"] < horas * 3600:
                    continue
                if ahora - r["ts"] > horas * 3600 + 2 * 3600:
                    r[campo] = None  # el sistema estaba apagado justo en ese momento: sin dato
                else:
                    precio = precio if precio is not None else self._precio_btc()
                    if precio is None:
                        return
                    r[campo] = round((precio - r["btc"]) / r["btc"] * 100, 2)
                cambio = True
        if cambio:
            self._guardar_registro()

    def _guardar_registro(self):
        try:
            os.makedirs(os.path.dirname(self.ruta_registro), exist_ok=True)
            tmp = self.ruta_registro + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.registro, f, ensure_ascii=False)
            os.replace(tmp, self.ruta_registro)
        except OSError as e:
            log.warning("Radar: no pude guardar el registro de noticias: %s", e)

    def texto_noticias(self) -> str:
        """Resumen del registro: después de cada tipo de noticia, ¿Bitcoin subió o bajó?"""
        if not self.registro:
            return ("🗞 Registro de noticias: todavía vacío. Cada noticia importante queda anotada con lo que hizo "
                    "Bitcoin 1, 4 y 24 horas después.")
        lineas = [f"🗞 Registro de noticias: {len(self.registro)} anotadas desde "
                  f"{datetime.fromtimestamp(self.registro[0]['ts'], tz=timezone.utc).strftime('%d/%m')}.",
                  "Qué hizo Bitcoin después (promedio y cuántas veces subió):"]
        for tipo in sorted({r["tipo"] for r in self.registro}):
            partes = []
            for horas in PLAZOS_HORAS:
                movs = [r[f"mov_{horas}h"] for r in self.registro
                        if r["tipo"] == tipo and r.get(f"mov_{horas}h") is not None]
                if movs:
                    subio = sum(m > 0 for m in movs)
                    partes.append(f"{horas}h: {sum(movs) / len(movs):+.2f}% (subió {subio} de {len(movs)})")
            n = sum(r["tipo"] == tipo for r in self.registro)
            lineas.append(f"• {tipo} ({n}): " + (" · ".join(partes) if partes else "esperando datos"))
        lineas.append("Con pocas noticias no hay conclusión: hacen falta decenas por tipo para ver un patrón.")
        return "\n".join(lineas)

    # ------------------------------------------------------------------ revisión
    def revisar(self):
        try:
            self._seguimiento()
        except Exception as e:  # noqa: BLE001 - el registro nunca frena al radar
            log.warning("Radar (registro): %s", e)
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
            if cuando <= ahora < hasta:
                self._anotar(clave, "dato económico EE.UU.", titulo)
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
                grave = any(_contiene(texto, p) for p in graves)
                if grave or any(_contiene(texto, p) for p in importantes):
                    tipo = ("noticia grave (pausa)" if grave and self._afecta_mercado(texto) else
                            "noticia grave (puntual)" if grave else "noticia importante")
                    self._anotar(f"news-{enlace}", tipo, titulo)
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
