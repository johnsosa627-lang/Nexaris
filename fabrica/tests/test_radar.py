import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from fabrica.config import cargar_config
from fabrica.radar import Radar, leer_rss
from tests.test_vivo import MercadoFalso, cfg_prueba, liga_papel, registro


def _ts(texto):
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc).timestamp()


RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Major exchange hacked, $200M stolen</title><link>https://n/1</link><pubDate>Tue, 13 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>SEC delays decision on new ETF</title><link>https://n/2</link><pubDate>Tue, 13 Oct 2026 14:10:00 GMT</pubDate></item>
<item><title>Bitcoin price analysis for the week</title><link>https://n/3</link><pubDate>Tue, 13 Oct 2026 14:20:00 GMT</pubDate></item>
<item><title>Scammer gets scammed in Ledger spy-chip exploit, loses almost $5 million in bitcoin</title><link>https://n/5</link><pubDate>Tue, 13 Oct 2026 14:30:00 GMT</pubDate></item>
<item><title>Old hack from last month</title><link>https://n/4</link><pubDate>Sun, 13 Sep 2026 14:20:00 GMT</pubDate></item>
</channel></rss>"""

CALENDARIO = [
    {"title": "CPI m/m", "country": "USD", "impact": "High", "date": "2026-10-13T12:30:00+00:00"},
    {"title": "Retail Sales", "country": "EUR", "impact": "High", "date": "2026-10-13T12:00:00+00:00"},
    {"title": "Minor data", "country": "USD", "impact": "Low", "date": "2026-10-13T12:00:00+00:00"},
]


class Resp:
    def __init__(self, texto):
        self.text = texto

    def raise_for_status(self):
        pass


def http(fng=50):
    def get(url, timeout, headers):
        if "faireconomy" in url:
            return Resp(json.dumps(CALENDARIO))
        if "alternative.me" in url:
            return Resp(json.dumps({"data": [{"value": str(fng)}]}))
        return Resp(RSS)
    return get


def velas_btc(cambio_pct, ahora):
    ts0 = int(ahora * 1000) // 300_000 * 300_000 - 5 * 300_000
    precios = [100.0, 100.0, 100.0 * (1 + cambio_pct / 200), 100.0 * (1 + cambio_pct / 100)]
    filas = [{"ts": ts0 + i * 300_000, "open": p, "high": p, "low": p, "close": p, "volume": 1} for i, p in enumerate(precios)]
    return pd.DataFrame(filas)


class MercadoBTC(MercadoFalso):
    def __init__(self, velas):
        super().__init__()
        self.v = velas

    def velas(self, simbolo, tf, limite, ahora_ms):
        return self.v


def armar(ahora, cambio_btc=0.0, fng=50, solo=None):
    cfg = cargar_config()
    if solo:
        for k in ("calendario", "bitcoin", "noticias", "miedo"):
            cfg["radar"][k] = k in solo
    estado, msgs, t = {}, [], {"ahora": ahora}
    r = Radar(cfg, estado, MercadoBTC(velas_btc(cambio_btc, ahora)), msgs.append, reloj=lambda: t["ahora"], http_get=http(fng))
    return r, estado, msgs, t


def test_leer_rss():
    items = leer_rss(RSS)
    assert len(items) == 5 and items[0][0].startswith("Major exchange") and items[0][1] == "https://n/1"
    assert items[0][2] == _ts("2026-10-13T14:00:00")


def test_dato_economico_avisa_antes_y_pausa_alrededor():
    r, estado, msgs, t = armar(_ts("2026-10-13T11:40:00"), solo=["calendario"])
    r.revisar()
    assert r.bloqueo() is None and any("CPI m/m" in m and "12:30 UTC" in m for m in msgs)  # aviso 50 min antes
    t["ahora"] = _ts("2026-10-13T12:10:00")
    r.revisar()
    assert "CPI" in r.bloqueo()
    t["ahora"] = _ts("2026-10-13T13:01:00")
    r.revisar()
    assert r.bloqueo() is None
    assert sum("CPI" in m for m in msgs) == 2  # un aviso previo y uno de pausa, sin repetir
    assert not any("Retail" in m or "Minor" in m for m in msgs)  # solo EE.UU. y de alto impacto


def test_bitcoin_brusco_pausa():
    r, _, msgs, t = armar(_ts("2026-10-13T15:00:00"), cambio_btc=-4.0, solo=["bitcoin"])
    r.revisar()
    assert "Bitcoin se movió -4.0%" in r.bloqueo() and any("🌪" in m for m in msgs)
    r2, _, msgs2, _ = armar(_ts("2026-10-13T15:00:00"), cambio_btc=1.0, solo=["bitcoin"])
    r2.revisar()
    assert r2.bloqueo() is None and msgs2 == []


def test_noticias_graves_pausan_e_importantes_solo_avisan():
    r, _, msgs, t = armar(_ts("2026-10-13T15:00:00"), solo=["noticias"])
    r.revisar()
    assert "noticia grave" in r.bloqueo()
    assert any("🚨" in m and "hacked" in m for m in msgs) and any("📰" in m and "SEC" in m for m in msgs)
    assert not any("price analysis" in m for m in msgs) and not any("Old hack" in m for m in msgs)
    # un caso puntual (5 millones, sin exchange ni stablecoin) solo avisa: no es el motivo de la pausa
    assert any("Scammer" in m and "solo aviso" in m and "🚨" not in m for m in msgs)
    assert "Scammer" not in r.bloqueo()
    n = len(msgs)
    r.revisar()
    assert len(msgs) == n  # no repite avisos


def test_miedo_extremo_avisa_y_una_fuente_caida_no_frena():
    r, _, msgs, _ = armar(_ts("2026-10-13T15:00:00"), fng=8, solo=["miedo", "calendario"])
    r.get = lambda url, timeout, headers: (_ for _ in ()).throw(ConnectionError("caído")) if "faireconomy" in url else http(8)(url, timeout, headers)
    r.revisar()
    assert any("MIEDO EXTREMO" in m for m in msgs) and "8/100" in r.texto()


def test_la_liga_no_abre_titulares_durante_la_pausa_del_radar(tmp_path):
    v = pd.DataFrame({"ts": [0], "open": [100.0], "high": [100.5], "low": [99.5], "close": [100.0], "volume": [1.0]})
    liga, _, t = liga_papel(tmp_path, cfg_prueba(max_titulares=1))
    liga.sincronizar_banco([registro(1), registro(2, "BBB/USDT:USDT")])
    liga.completar_titulares()
    liga.e["radar"] = {"hasta": t["ahora"] + 600, "motivo": "Bitcoin se movió -5%"}
    assert "radar externo" in liga.puede_operar()
    tit, sup = liga.e["bots"]["bot1"], liga.e["bots"]["bot2"]
    liga._abrir(tit, 1, 0.5, v.iloc[-1].to_dict())
    liga._abrir(sup, 1, 0.5, v.iloc[-1].to_dict())
    assert tit["posicion"] is None and sup["posicion"] is not None  # los suplentes siguen practicando
    t["ahora"] += 601
    assert liga.puede_operar() is None
