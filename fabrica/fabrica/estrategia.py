"""Estrategias armadas con piezas: 1 condición "disparador" + hasta 2 filtros + salidas.

Una estrategia es un diccionario JSON. Las reglas se escriben para COMPRAR (long);
para VENDER EN CORTO (short) se usa automáticamente la regla espejo.
"""
import copy
import hashlib
import json

import numpy as np
import pandas as pd

from . import indicadores as ind

# Valores permitidos (discretos: estrategias simples y cálculos reutilizables)
MEDIAS = [5, 8, 10, 13, 20, 21, 30, 34, 50, 55, 89, 100, 144, 200]
RSI_N = [7, 14, 21]
RSI_CRUCE = [20, 25, 30, 40, 50, 60]
RSI_FILTRO = [30, 40, 45, 50, 55, 60, 70]
ADX_NIVEL = [15, 20, 25, 30, 40]
DONCHIAN = [10, 20, 30, 55, 100]
BOLL = [(20, 2.0), (20, 2.5), (50, 2.0)]
MACD = [(12, 26, 9), (8, 21, 5), (5, 35, 5)]
VOL_MULT = [1.0, 1.2, 1.5, 2.0]
# "rango": stop debajo del mínimo de las últimas N velas (estructura), con un margen de 0,25 ATR
STOP = {"pct": [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0], "atr": [1.0, 1.5, 2.0, 2.5, 3.0, 4.0],
        "rango": [5, 10, 20, 30]}
TP = {"pct": [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0], "atr": [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]}
TRAILING = {"pct": [1.0, 2.0, 3.0], "atr": [1.5, 2.0, 3.0, 4.0], "rango": [1.5, 2.0, 3.0, 4.0]}  # rango: en ATR
MAX_VELAS = [12, 24, 48, 96, 200]
RSI_CORTO_N = [2, 3]                       # RSI muy corto: retrocesos de 1-3 velas
RSI_CORTO_NIVEL = [5, 10, 15, 20]
COMPRESION = [(20, 50), (20, 100), (50, 100)]  # (Bollinger, velas en las que su ancho es el menor)
HORARIOS = ["asia", "europa", "america"]   # 0-8, 8-16 y 16-24 hora UTC
HORAS = {"asia": (0, 8), "europa": (8, 16), "america": (16, 24)}
VOLATILIDAD = [0.7, 1.0, 1.3]              # ATR actual / su promedio de 100 velas
SUPERTREND = [(7, 3.0), (10, 2.0), (10, 3.0), (14, 3.0)]
ICHIMOKU = [(9, 26, 52), (10, 30, 60), (20, 60, 120)]  # clásico, cripto y lento
RANGO_N = [20, 30, 50]                     # velas de la consolidación
# Rupturas de apertura de sesión (hora local de cada plaza, con horario de verano). m = minutos del rango inicial.
SESIONES = {
    "nueva_york": {"zona": "America/New_York", "hora": (9, 30), "minutos": [15, 30, 60], "habiles": True},
    "londres": {"zona": "Europe/London", "hora": (8, 0), "minutos": [15, 30, 60], "habiles": True},
    "asia": {"zona": "UTC", "hora": (0, 0), "minutos": [480], "habiles": False},  # rango 0-8 UTC, se rompe en Londres
}
VENTANA_APERTURA_MIN = 240                 # se busca la ruptura en las 4 horas siguientes al rango
RANGO_ANCHO = [3.0, 4.0, 6.0]              # alto máximo del rango, en ATR (más chico = más quieto)

DISPARADORES = ["cruce_medias", "cruce_precio_media", "cruce_macd", "ruptura_donchian", "rebote_bollinger", "rsi_cruce",
                "retroceso_rsi", "ruptura_compresion", "cambio_supertrend", "ruptura_nube", "ruptura_rango", "ruptura_apertura"]
FILTROS = ["tendencia", "rsi_filtro", "adx_filtro", "volumen_filtro", "di_filtro",
           "funding_filtro", "btc_tendencia", "miedo_codicia", "horario", "volatilidad"]
# Datos de afuera del gráfico: la fábrica los prueba igual que todo; si no sirven, los descarta
EXTERNOS = {"funding_filtro", "btc_tendencia", "miedo_codicia"}
FUNDING_NIVEL = [-0.01, 0.0, 0.01, 0.03]   # % por cada 8 horas
FNG_NIVEL = [20, 30, 40, 50, 60, 70, 80]


# ------------------------------------------------------------------ cálculo de indicadores con memoria
class Contexto:
    """Guarda los indicadores ya calculados para no repetirlos entre estrategias."""

    def __init__(self, velas: pd.DataFrame, externos: dict = None):
        self.velas = velas.reset_index(drop=True)
        self.o, self.h, self.l, self.c, self.v = (self.velas[k] for k in ("open", "high", "low", "close", "volume"))
        self._cache = {}
        self.externos = {k: pd.Series(np.asarray(v, dtype=float)) for k, v in (externos or {}).items()
                         if v is not None and len(v) == len(self.velas)}

    def ind(self, *clave):
        if clave not in self._cache:
            self._cache[clave] = self._calcular(clave)
        return self._cache[clave]

    def _calcular(self, k):
        t = k[0]
        if t == "ema":
            return ind.ema(self.c, k[1])
        if t == "sma":
            return ind.sma(self.c, k[1])
        if t == "rsi":
            return ind.rsi(self.c, k[1])
        if t in ("adx", "dip", "dim"):
            a, p, m = ind.adx(self.h, self.l, self.c, k[1])
            self._cache[("adx", k[1])], self._cache[("dip", k[1])], self._cache[("dim", k[1])] = a, p, m
            return {"adx": a, "dip": p, "dim": m}[t]
        if t in ("macd", "macds"):
            linea, sen, _ = ind.macd(self.c, *k[1:])
            self._cache[("macd",) + k[1:]], self._cache[("macds",) + k[1:]] = linea, sen
            return linea if t == "macd" else sen
        if t in ("bbs", "bbi"):
            sup, _, inf = ind.bollinger(self.c, k[1], k[2])
            self._cache[("bbs", k[1], k[2])], self._cache[("bbi", k[1], k[2])] = sup, inf
            return sup if t == "bbs" else inf
        if t == "dch":  # máximo de las n velas ANTERIORES
            return self.h.rolling(k[1]).max().shift(1)
        if t == "dcl":
            return self.l.rolling(k[1]).min().shift(1)
        if t == "volsma":
            return ind.sma(self.v, k[1])
        if t == "atr":
            return ind.atr(self.h, self.l, self.c, k[1])
        if t == "bbancho":  # ancho de Bollinger relativo al precio
            sup, _, inf = ind.bollinger(self.c, k[1], 2.0)
            return (sup - inf) / self.c.abs()
        if t == "atr_rel":  # ATR de hoy comparado con su promedio de 100 velas
            a = self.ind("atr", 14)
            return a / a.rolling(100).mean()
        if t == "supertrend":
            return ind.supertrend(self.h, self.l, self.c, k[1], k[2])
        if t in ("nube_techo", "nube_piso"):
            techo, piso = ind.ichimoku_nube(self.h, self.l, *k[1:])
            self._cache[("nube_techo",) + k[1:]], self._cache[("nube_piso",) + k[1:]] = techo, piso
            return techo if t == "nube_techo" else piso
        if t == "rango_alto":  # alto del rango de las n velas ANTERIORES, medido en ATR de la vela anterior
            return (self.ind("dch", k[1]) - self.ind("dcl", k[1])) / self.ind("atr", 14).shift(1)
        if t == "dist_rango":  # distancia del cierre al borde opuesto de las últimas n velas + 0,25 ATR
            a = self.ind("atr", 14)
            if k[2] == 1:
                d = self.c - self.l.rolling(k[1]).min()
            else:
                d = self.h.rolling(k[1]).max() - self.c
            return np.maximum(d + 0.25 * a, 0.5 * a)  # nunca un stop pegado al precio
        if t in ("ap_alto", "ap_bajo", "ap_ventana"):
            alto, bajo, ventana = self._apertura(k[1], k[2])
            self._cache[("ap_alto",) + k[1:]], self._cache[("ap_bajo",) + k[1:]] = alto, bajo
            self._cache[("ap_ventana",) + k[1:]] = ventana
            return {"ap_alto": alto, "ap_bajo": bajo, "ap_ventana": ventana}[t]
        if t == "hora":
            ts = self.velas["ts"] if "ts" in self.velas else pd.Series(np.full(len(self.velas), np.nan))
            return (ts // 3_600_000) % 24
        if t == "ext":  # dato externo (si falta, todo NaN: la condición no se cumple nunca)
            return self.externos.get(k[1], pd.Series(np.full(len(self.velas), np.nan)))
        if t == "ext_ema":
            return self.ind("ext", k[1]).ewm(span=k[2], adjust=False, min_periods=k[2]).mean()
        raise ValueError(f"Indicador desconocido: {k}")


    def _apertura(self, sesion: str, minutos: int):
        """Máximo y mínimo del rango inicial de la sesión de cada día, y en qué velas vale buscar la ruptura.

        Solo usa velas ya terminadas: el rango se completa antes de que se abra la ventana de ruptura.
        """
        cfg = SESIONES[sesion]
        n = len(self.velas)
        if "ts" not in self.velas or n == 0:
            nan = pd.Series(np.full(n, np.nan))
            return nan, nan, np.zeros(n, dtype=bool)
        ts = self.velas["ts"].astype("int64")
        paso = int(ts.diff().median()) if n > 1 else 0
        local = pd.to_datetime(ts, unit="ms", utc=True).dt.tz_convert(cfg["zona"])
        dia = local.dt.tz_localize(None).dt.normalize()
        h, m = cfg["hora"]
        apertura = (dia + pd.Timedelta(hours=h, minutes=m)).dt.tz_localize(cfg["zona"], ambiguous="NaT",
                                                                          nonexistent="NaT")
        ap_ms = (apertura - pd.Timestamp(0, tz="UTC")) / pd.Timedelta(milliseconds=1)  # NaN si la hora no existe
        fin_rango = ap_ms + minutos * 60_000
        en_rango = (ts >= ap_ms) & (ts + paso <= fin_rango)
        habil = local.dt.weekday < 5 if cfg["habiles"] else pd.Series(True, index=ts.index)
        clave = dia.astype("int64")
        alto = self.h.where(en_rango).groupby(clave).transform("max")
        bajo = self.l.where(en_rango).groupby(clave).transform("min")
        completo = en_rango.groupby(clave).transform("sum") * paso >= minutos * 60_000  # el rango tiene todas sus velas
        ventana = (ts >= fin_rango) & (ts + paso <= fin_rango + VENTANA_APERTURA_MIN * 60_000) & habil & completo
        return alto, bajo, ventana.fillna(False).to_numpy(dtype=bool)


def _cruza_arriba(a, b):
    return ((a > b) & (a.shift(1) <= b.shift(1))).to_numpy()


def _cruza_abajo(a, b):
    return ((a < b) & (a.shift(1) >= b.shift(1))).to_numpy()


def _comparar(a, op, b):
    return (a > b).to_numpy() if op == ">" else (a < b).to_numpy()


def _invertir(op):
    return "<" if op == ">" else ">"


def condicion(ctx: Contexto, cond: dict, lado: int) -> np.ndarray:
    """Evalúa una condición. lado=+1 regla de compra, lado=-1 su espejo para venta en corto."""
    t = cond["tipo"]
    cruza = _cruza_arriba if lado == 1 else _cruza_abajo
    if t == "cruce_medias":
        return cruza(ctx.ind(cond["media"], cond["rapida"]), ctx.ind(cond["media"], cond["lenta"]))
    if t == "cruce_precio_media":
        return cruza(ctx.c, ctx.ind(cond["media"], cond["n"]))
    if t == "cruce_macd":
        p = (cond["rapida"], cond["lenta"], cond["senal"])
        return cruza(ctx.ind("macd", *p), ctx.ind("macds", *p))
    if t == "ruptura_donchian":
        nivel = ctx.ind("dch", cond["n"]) if lado == 1 else ctx.ind("dcl", cond["n"])
        return cruza(ctx.c, nivel)
    if t == "rebote_bollinger":
        banda = ctx.ind("bbi", cond["n"], cond["k"]) if lado == 1 else ctx.ind("bbs", cond["n"], cond["k"])
        return cruza(ctx.c, banda)
    if t == "rsi_cruce":
        nivel = cond["nivel"] if lado == 1 else 100 - cond["nivel"]
        return cruza(ctx.ind("rsi", cond["n"]), pd.Series(nivel, index=ctx.c.index))
    if t == "retroceso_rsi":  # compra un retroceso corto (RSI de 2-3 velas sale de sobreventa)
        nivel = cond["nivel"] if lado == 1 else 100 - cond["nivel"]
        return cruza(ctx.ind("rsi", cond["n"]), pd.Series(nivel, index=ctx.c.index))
    if t == "ruptura_compresion":  # mercado "dormido" (bandas muy angostas) que se despierta con fuerza
        ancho = ctx.ind("bbancho", cond["n"])
        dormido = (ancho.shift(1) <= ancho.shift(1).rolling(cond["m"]).min()).to_numpy()
        banda = ctx.ind("bbs", cond["n"], 2.0) if lado == 1 else ctx.ind("bbi", cond["n"], 2.0)
        return dormido & cruza(ctx.c, banda)
    if t == "cambio_supertrend":  # el Supertrend da vuelta a alcista (espejo: a bajista)
        d = ctx.ind("supertrend", cond["n"], cond["k"])
        return ((d == lado) & (d.shift(1) == -lado)).to_numpy()
    if t == "ruptura_nube":  # el precio sale por arriba de la nube de Ichimoku (espejo: por abajo)
        p = (cond["t"], cond["k"], cond["s"])
        return cruza(ctx.c, ctx.ind("nube_techo", *p) if lado == 1 else ctx.ind("nube_piso", *p))
    if t == "ruptura_rango":  # rango angosto (consolidación) y cierre que lo rompe
        quieto = (ctx.ind("rango_alto", cond["n"]) <= cond["ancho"]).to_numpy()
        nivel = ctx.ind("dch", cond["n"]) if lado == 1 else ctx.ind("dcl", cond["n"])
        return quieto & cruza(ctx.c, nivel)
    if t == "ruptura_apertura":  # rompe el máximo del rango inicial de la sesión (espejo: el mínimo)
        p = (cond["sesion"], cond["m"])
        nivel = ctx.ind("ap_alto", *p) if lado == 1 else ctx.ind("ap_bajo", *p)
        return ctx.ind("ap_ventana", *p) & cruza(ctx.c, nivel)
    if t == "horario":  # simétrico: solo opera en ese tramo del día
        desde, hasta = HORAS[cond["tramo"]]
        h = ctx.ind("hora")
        return ((h >= desde) & (h < hasta)).to_numpy()
    if t == "volatilidad":  # simétrico: mercado más movido (>) o más tranquilo (<) que lo normal
        return _comparar(ctx.ind("atr_rel"), cond["op"], cond["nivel"])
    if t == "tendencia":
        return _comparar(ctx.c, ">" if lado == 1 else "<", ctx.ind(cond["media"], cond["n"]))
    if t == "rsi_filtro":
        op = cond["op"] if lado == 1 else _invertir(cond["op"])
        nivel = cond["nivel"] if lado == 1 else 100 - cond["nivel"]
        return _comparar(ctx.ind("rsi", cond["n"]), op, nivel)
    if t == "adx_filtro":  # simétrico: mide fuerza de tendencia, no dirección
        return _comparar(ctx.ind("adx", 14), cond["op"], cond["nivel"])
    if t == "volumen_filtro":
        return (ctx.v > ctx.ind("volsma", 20) * cond["mult"]).to_numpy()
    if t == "di_filtro":
        a, b = (ctx.ind("dip", 14), ctx.ind("dim", 14)) if lado == 1 else (ctx.ind("dim", 14), ctx.ind("dip", 14))
        return (a > b).to_numpy()
    if t == "funding_filtro":  # compra si los que apuestan a la suba no están pagando de más (y espejo)
        f = ctx.ind("ext", "funding")
        return (f < cond["nivel"]).to_numpy() if lado == 1 else (f > -cond["nivel"]).to_numpy()
    if t == "btc_tendencia":  # Bitcoin como líder del mercado
        btc, media = ctx.ind("ext", "btc"), ctx.ind("ext_ema", "btc", cond["n"])
        return (btc > media).to_numpy() if lado == 1 else (btc < media).to_numpy()
    if t == "miedo_codicia":
        op = cond["op"] if lado == 1 else _invertir(cond["op"])
        nivel = cond["nivel"] if lado == 1 else 100 - cond["nivel"]
        return _comparar(ctx.ind("ext", "fng"), op, nivel)
    raise ValueError(f"Condición desconocida: {t}")


def senales_crudas(ctx: Contexto, est: dict):
    """(compra, venta) de las reglas sin mirar el lado permitido: sirve para la salida por señal contraria."""
    resultado = []
    for lado in (1, -1):
        s = np.ones(len(ctx.velas), dtype=bool)
        for cond in est["reglas"]:
            s &= condicion(ctx, cond, lado)
        resultado.append(s)
    return resultado[0], resultado[1]


def senales(ctx: Contexto, est: dict):
    """Devuelve (entradas_long, entradas_short) como arrays booleanos."""
    n = len(ctx.velas)
    resultado = []
    for lado, habilitado in ((1, est["lado"] in ("ambos", "long")), (-1, est["lado"] in ("ambos", "short"))):
        if not habilitado:
            resultado.append(np.zeros(n, dtype=bool))
            continue
        s = np.ones(n, dtype=bool)
        for cond in est["reglas"]:
            s &= condicion(ctx, cond, lado)
        resultado.append(s)
    return resultado[0], resultado[1]


# ------------------------------------------------------------------ creación aleatoria
def _elegir(rng, lista):
    return lista[int(rng.integers(len(lista)))]


def condicion_aleatoria(rng, tipo: str) -> dict:
    if tipo == "cruce_medias":
        a, b = sorted(rng.choice(len(MEDIAS), 2, replace=False))
        return {"tipo": tipo, "media": _elegir(rng, ["ema", "sma"]), "rapida": MEDIAS[a], "lenta": MEDIAS[b]}
    if tipo == "cruce_precio_media":
        return {"tipo": tipo, "media": _elegir(rng, ["ema", "sma"]), "n": _elegir(rng, MEDIAS)}
    if tipo == "cruce_macd":
        r, l, s = _elegir(rng, MACD)
        return {"tipo": tipo, "rapida": r, "lenta": l, "senal": s}
    if tipo == "ruptura_donchian":
        return {"tipo": tipo, "n": _elegir(rng, DONCHIAN)}
    if tipo == "rebote_bollinger":
        n, k = _elegir(rng, BOLL)
        return {"tipo": tipo, "n": n, "k": k}
    if tipo == "rsi_cruce":
        return {"tipo": tipo, "n": _elegir(rng, RSI_N), "nivel": _elegir(rng, RSI_CRUCE)}
    if tipo == "retroceso_rsi":
        return {"tipo": tipo, "n": _elegir(rng, RSI_CORTO_N), "nivel": _elegir(rng, RSI_CORTO_NIVEL)}
    if tipo == "ruptura_compresion":
        n, m = _elegir(rng, COMPRESION)
        return {"tipo": tipo, "n": n, "m": m}
    if tipo == "cambio_supertrend":
        n, k = _elegir(rng, SUPERTREND)
        return {"tipo": tipo, "n": n, "k": k}
    if tipo == "ruptura_nube":
        t, k, s_ = _elegir(rng, ICHIMOKU)
        return {"tipo": tipo, "t": t, "k": k, "s": s_}
    if tipo == "ruptura_rango":
        return {"tipo": tipo, "n": _elegir(rng, RANGO_N), "ancho": _elegir(rng, RANGO_ANCHO)}
    if tipo == "ruptura_apertura":
        sesion = _elegir(rng, list(SESIONES))
        return {"tipo": tipo, "sesion": sesion, "m": _elegir(rng, SESIONES[sesion]["minutos"])}
    if tipo == "horario":
        return {"tipo": tipo, "tramo": _elegir(rng, HORARIOS)}
    if tipo == "volatilidad":
        return {"tipo": tipo, "op": _elegir(rng, [">", "<"]), "nivel": _elegir(rng, VOLATILIDAD)}
    if tipo == "tendencia":
        return {"tipo": tipo, "media": _elegir(rng, ["ema", "sma"]), "n": _elegir(rng, MEDIAS[4:])}
    if tipo == "rsi_filtro":
        return {"tipo": tipo, "n": _elegir(rng, RSI_N), "op": _elegir(rng, [">", "<"]), "nivel": _elegir(rng, RSI_FILTRO)}
    if tipo == "adx_filtro":
        return {"tipo": tipo, "op": _elegir(rng, [">", "<"]), "nivel": _elegir(rng, ADX_NIVEL)}
    if tipo == "volumen_filtro":
        return {"tipo": tipo, "mult": _elegir(rng, VOL_MULT)}
    if tipo == "di_filtro":
        return {"tipo": tipo}
    if tipo == "funding_filtro":
        return {"tipo": tipo, "nivel": _elegir(rng, FUNDING_NIVEL)}
    if tipo == "btc_tendencia":
        return {"tipo": tipo, "n": _elegir(rng, MEDIAS[4:])}
    if tipo == "miedo_codicia":
        return {"tipo": tipo, "op": _elegir(rng, [">", "<"]), "nivel": _elegir(rng, FNG_NIVEL)}
    raise ValueError(tipo)


def salidas_aleatorias(rng) -> dict:
    st = _elegir(rng, ["pct", "atr", "atr", "rango"])
    tp_tipo = _elegir(rng, ["pct", "pct", "atr", "ninguno"]) if st == "pct" else _elegir(rng, ["pct", "atr", "atr", "ninguno"])
    con_trailing = rng.random() < 0.3 or tp_tipo == "ninguno"
    s = {
        "stop_tipo": st, "stop": _elegir(rng, STOP[st]),
        "tp_tipo": tp_tipo, "tp": _elegir(rng, TP[tp_tipo]) if tp_tipo != "ninguno" else 0.0,
        "trailing": _elegir(rng, TRAILING[st]) if con_trailing else 0.0,
        "max_velas": _elegir(rng, MAX_VELAS) if rng.random() < 0.3 else 0,
    }
    if rng.random() < 0.15:  # la clave solo aparece si está activa (no cambia el id de las estrategias viejas)
        s["salida_contraria"] = True
    return s


def estrategia_aleatoria(rng, max_filtros: int = 2) -> dict:
    reglas = [condicion_aleatoria(rng, _elegir(rng, DISPARADORES))]
    n_filtros = int(rng.integers(0, max_filtros + 1))
    for tipo in rng.choice(FILTROS, n_filtros, replace=False):
        reglas.append(condicion_aleatoria(rng, str(tipo)))
    return {"lado": _elegir(rng, ["ambos", "ambos", "long", "short"]), "reglas": reglas,
            "salidas": salidas_aleatorias(rng)}


# ------------------------------------------------------------------ genética
def _vecino(rng, lista, valor):
    """Valor de al lado en la lista (para "mover un poco" un parámetro)."""
    if valor not in lista or len(lista) < 2:
        return _elegir(rng, lista)
    i = lista.index(valor)
    paso = int(rng.choice([-1, 1]))
    if not 0 <= i + paso < len(lista):
        paso = -paso  # en el borde: moverse hacia adentro
    return lista[i + paso]


def _mover_condicion(rng, cond: dict) -> dict:
    c = dict(cond)
    t = c["tipo"]
    if t == "cruce_medias":
        if rng.random() < 0.5:
            c["rapida"] = _vecino(rng, MEDIAS, c["rapida"])
        else:
            c["lenta"] = _vecino(rng, MEDIAS, c["lenta"])
        if c["rapida"] >= c["lenta"]:
            c = dict(cond)
            c["lenta"] = MEDIAS[min(MEDIAS.index(c["lenta"]) + 1, len(MEDIAS) - 1)]
            if c["rapida"] >= c["lenta"]:
                c["rapida"] = MEDIAS[MEDIAS.index(c["rapida"]) - 1]
    elif t in ("cruce_precio_media", "tendencia"):
        c["n"] = _vecino(rng, MEDIAS if t == "cruce_precio_media" else MEDIAS[4:], c["n"])
    elif t == "cruce_macd":
        c["rapida"], c["lenta"], c["senal"] = _vecino(rng, MACD, (c["rapida"], c["lenta"], c["senal"]))
    elif t == "ruptura_donchian":
        c["n"] = _vecino(rng, DONCHIAN, c["n"])
    elif t == "rebote_bollinger":
        c["n"], c["k"] = _vecino(rng, BOLL, (c["n"], c["k"]))
    elif t == "rsi_cruce":
        clave = "n" if rng.random() < 0.3 else "nivel"
        c[clave] = _vecino(rng, RSI_N if clave == "n" else RSI_CRUCE, c[clave])
    elif t == "rsi_filtro":
        clave = "n" if rng.random() < 0.3 else "nivel"
        c[clave] = _vecino(rng, RSI_N if clave == "n" else RSI_FILTRO, c[clave])
    elif t == "adx_filtro":
        c["nivel"] = _vecino(rng, ADX_NIVEL, c["nivel"])
    elif t == "volumen_filtro":
        c["mult"] = _vecino(rng, VOL_MULT, c["mult"])
    elif t == "funding_filtro":
        c["nivel"] = _vecino(rng, FUNDING_NIVEL, c["nivel"])
    elif t == "btc_tendencia":
        c["n"] = _vecino(rng, MEDIAS[4:], c["n"])
    elif t == "miedo_codicia":
        c["nivel"] = _vecino(rng, FNG_NIVEL, c["nivel"])
    elif t == "retroceso_rsi":
        clave = "n" if rng.random() < 0.3 else "nivel"
        c[clave] = _vecino(rng, RSI_CORTO_N if clave == "n" else RSI_CORTO_NIVEL, c[clave])
    elif t == "ruptura_compresion":
        c["n"], c["m"] = _vecino(rng, COMPRESION, (c["n"], c["m"]))
    elif t == "cambio_supertrend":
        c["n"], c["k"] = _vecino(rng, SUPERTREND, (c["n"], c["k"]))
    elif t == "ruptura_nube":
        c["t"], c["k"], c["s"] = _vecino(rng, ICHIMOKU, (c["t"], c["k"], c["s"]))
    elif t == "ruptura_rango":
        clave = "n" if rng.random() < 0.5 else "ancho"
        c[clave] = _vecino(rng, RANGO_N if clave == "n" else RANGO_ANCHO, c[clave])
    elif t == "ruptura_apertura":
        c["m"] = _vecino(rng, SESIONES[c["sesion"]]["minutos"], c["m"])
    elif t == "horario":
        c["tramo"] = _vecino(rng, HORARIOS, c["tramo"])
    elif t == "volatilidad":
        c["nivel"] = _vecino(rng, VOLATILIDAD, c["nivel"])
    return c


def _mover_salidas(rng, s: dict) -> dict:
    s = dict(s)
    opciones = ["stop"] + (["tp"] if s["tp_tipo"] != "ninguno" else []) + \
        (["trailing"] if s["trailing"] > 0 else []) + (["max_velas"] if s["max_velas"] > 0 else [])
    opcion = _elegir(rng, opciones)
    if opcion == "stop":
        s["stop"] = _vecino(rng, STOP[s["stop_tipo"]], s["stop"])
    elif opcion == "tp" and s["tp_tipo"] != "ninguno":
        s["tp"] = _vecino(rng, TP[s["tp_tipo"]], s["tp"])
    elif opcion == "trailing" and s["trailing"] > 0:
        s["trailing"] = _vecino(rng, TRAILING[s["stop_tipo"]], s["trailing"])
    elif opcion == "max_velas" and s["max_velas"] > 0:
        s["max_velas"] = _vecino(rng, MAX_VELAS, s["max_velas"])
    return s


def _movible(c: dict) -> bool:
    """¿Tiene algún número que se pueda mover al valor vecino?"""
    if c["tipo"] == "di_filtro":
        return False
    if c["tipo"] == "ruptura_apertura":
        return len(SESIONES[c["sesion"]]["minutos"]) > 1
    return True


def perturbar(rng, est: dict, cambios: int = 1) -> dict:
    """Copia con 1-2 parámetros movidos al valor vecino (prueba de sobreajuste)."""
    e = copy.deepcopy(est)
    e.pop("famosa", None)  # ya no es la original
    for _ in range(cambios):
        objetivos = [i for i, c in enumerate(e["reglas"]) if _movible(c)] + ["salidas"]
        obj = objetivos[int(rng.integers(len(objetivos)))]
        if obj == "salidas":
            e["salidas"] = _mover_salidas(rng, e["salidas"])
        else:
            e["reglas"][obj] = _mover_condicion(rng, e["reglas"][obj])
    return e


def mutar(rng, est: dict, max_filtros: int = 2) -> dict:
    e = copy.deepcopy(est)
    e.pop("famosa", None)
    accion = _elegir(rng, ["mover", "mover", "salidas", "disparador", "filtro", "lado"])
    if accion == "mover":
        return perturbar(rng, e, 1)
    if accion == "salidas":
        e["salidas"] = salidas_aleatorias(rng)
    elif accion == "disparador":
        e["reglas"][0] = condicion_aleatoria(rng, _elegir(rng, DISPARADORES))
    elif accion == "filtro":
        filtros = e["reglas"][1:]
        tipos = {f["tipo"] for f in filtros}
        libres = [t for t in FILTROS if t not in tipos]
        if filtros and (len(filtros) >= max_filtros or rng.random() < 0.4):
            filtros.pop(int(rng.integers(len(filtros))))
        elif libres:
            filtros.append(condicion_aleatoria(rng, _elegir(rng, libres)))
        e["reglas"] = [e["reglas"][0]] + filtros
    else:
        e["lado"] = _elegir(rng, [x for x in ("ambos", "long", "short") if x != e["lado"]])
    return e


def cruzar(rng, a: dict, b: dict, max_filtros: int = 2) -> dict:
    """Hija que mezcla piezas de dos estrategias."""
    hija = {"lado": _elegir(rng, [a["lado"], b["lado"]]),
            "reglas": [copy.deepcopy(_elegir(rng, [a["reglas"][0], b["reglas"][0]]))],
            "salidas": copy.deepcopy(_elegir(rng, [a["salidas"], b["salidas"]]))}
    filtros, vistos = [], set()
    for f in a["reglas"][1:] + b["reglas"][1:]:
        if f["tipo"] not in vistos and rng.random() < 0.5:
            filtros.append(copy.deepcopy(f))
            vistos.add(f["tipo"])
    hija["reglas"] += filtros[:max_filtros]
    return hija


def identificador(est: dict) -> str:
    base = {k: est[k] for k in ("lado", "reglas", "salidas")}
    return hashlib.sha1(json.dumps(base, sort_keys=True).encode()).hexdigest()[:10]


# ------------------------------------------------------------------ explicación en español simple
def _media(c):
    return "media exponencial" if c["media"] == "ema" else "media simple"


def describir_condicion(c: dict) -> str:
    t = c["tipo"]
    if t == "cruce_medias":
        return f"la {_media(c)} de {c['rapida']} velas cruza hacia arriba la de {c['lenta']} velas"
    if t == "cruce_precio_media":
        return f"el precio cruza hacia arriba su {_media(c)} de {c['n']} velas"
    if t == "cruce_macd":
        return f"el MACD ({c['rapida']},{c['lenta']},{c['senal']}) cruza hacia arriba su línea de señal"
    if t == "ruptura_donchian":
        return f"el precio supera el máximo de las últimas {c['n']} velas"
    if t == "rebote_bollinger":
        return f"el precio vuelve a entrar por arriba de la banda inferior de Bollinger ({c['n']}, {c['k']})"
    if t == "rsi_cruce":
        return f"el RSI de {c['n']} velas sube por encima de {c['nivel']}"
    if t == "retroceso_rsi":
        return f"tras una caída corta, el RSI de {c['n']} velas vuelve a subir por encima de {c['nivel']} (compra el retroceso)"
    if t == "ruptura_compresion":
        return (f"después de un mercado quieto (bandas de Bollinger de {c['n']} velas en su punto más angosto de "
                f"las últimas {c['m']}), el precio rompe la banda superior")
    if t == "cambio_supertrend":
        return f"el Supertrend ({c['n']}, {c['k']}) pasa a alcista"
    if t == "ruptura_nube":
        return f"el precio sale por arriba de la nube de Ichimoku ({c['t']}, {c['k']}, {c['s']})"
    if t == "ruptura_rango":
        return (f"después de {c['n']} velas en un rango angosto (alto menor a {c['ancho']} ATR), "
                f"el precio cierra por encima del máximo del rango")
    if t == "ruptura_apertura":
        if c["sesion"] == "asia":
            return "el precio rompe por arriba el rango de la sesión de Asia (0 a 8 h UTC) en las 4 horas siguientes"
        plaza = {"nueva_york": "Nueva York (9:30)", "londres": "Londres (8:00)"}[c["sesion"]]
        return (f"el precio rompe por arriba el máximo de los primeros {c['m']} minutos de la apertura de {plaza}, "
                f"en las 4 horas siguientes")
    if t == "horario":
        desde, hasta = HORAS[c["tramo"]]
        return f"es horario de {c['tramo'].capitalize()} ({desde} a {hasta} h UTC)"
    if t == "volatilidad":
        return (f"el mercado se mueve {'más' if c['op'] == '>' else 'menos'} que {c['nivel']} veces "
                f"lo normal (ATR comparado con su promedio)")
    if t == "tendencia":
        return f"el precio está por encima de su {_media(c)} de {c['n']} velas (tendencia alcista)"
    if t == "rsi_filtro":
        return f"el RSI de {c['n']} velas está {'por encima' if c['op'] == '>' else 'por debajo'} de {c['nivel']}"
    if t == "adx_filtro":
        return f"el ADX (fuerza de la tendencia) está {'por encima' if c['op'] == '>' else 'por debajo'} de {c['nivel']}"
    if t == "volumen_filtro":
        return f"el volumen es mayor a {c['mult']} veces su promedio de 20 velas"
    if t == "di_filtro":
        return "los compradores dominan a los vendedores (+DI mayor que -DI)"
    if t == "funding_filtro":
        return f"el funding (lo que pagan los que apuestan a la suba) está por debajo de {c['nivel']}%"
    if t == "btc_tendencia":
        return f"Bitcoin está por encima de su media de {c['n']} velas (el líder del mercado sube)"
    if t == "miedo_codicia":
        return (f"el índice de Miedo y Codicia está {'por encima' if c['op'] == '>' else 'por debajo'} "
                f"de {c['nivel']} (0 = miedo extremo, 100 = codicia extrema)")
    return t


def describir(est: dict) -> str:
    reglas = describir_condicion(est["reglas"][0])
    if len(est["reglas"]) > 1:
        reglas += ", siempre que " + " y ".join(describir_condicion(c) for c in est["reglas"][1:])
    s = est["salidas"]
    unidad = (lambda x: f"{x}%") if s["stop_tipo"] == "pct" else (lambda x: f"{x} ATR")
    textos = {
        "ambos": f"Compra cuando {reglas}. Vende en corto en la situación opuesta (espejo).",
        "long": f"Solo compra: entra cuando {reglas}.",
        "short": f"Solo vende en corto: entra en la situación opuesta a cuando {reglas}.",
    }
    if s["stop_tipo"] == "rango":
        salida = f" Stop-loss debajo del mínimo de las últimas {int(s['stop'])} velas (más 0,25 ATR de margen)"
    else:
        salida = f" Stop-loss a {unidad(s['stop'])} del precio de entrada"
    if s["tp_tipo"] != "ninguno":
        salida += f", toma ganancia a {s['tp']}{'%' if s['tp_tipo'] == 'pct' else ' ATR'}"
    if s["trailing"]:
        salida += f", stop móvil a {unidad(s['trailing'])}"
    if s["max_velas"]:
        salida += f", y cierra sí o sí tras {s['max_velas']} velas"
    if s.get("salida_contraria"):
        salida += ", y sale antes si aparece la señal contraria"
    texto = textos[est["lado"]] + salida + "."
    if est.get("famosa"):
        texto = f"[Basada en una estrategia conocida: {est['famosa']}] " + texto
    if "ATR" in texto:
        texto += " (ATR = tamaño promedio de las velas.)"
    return texto
