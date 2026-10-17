import json
import os
from datetime import datetime, timezone

import pytest

from fabrica.servicio import Servicio
from fabrica.telegram import Telegram
from tests.conftest import H, serie_mercado
from tests.test_vivo import MercadoFalso, cfg_prueba, liga_papel, registro


class Proceso:
    def __init__(self):
        self.listo = False

    def poll(self):
        return 0 if self.listo else None


class Hilo:
    def is_alive(self):
        return False


def armar(tmp_path, ahora):
    cfg = cfg_prueba()
    cfg["radar"]["activo"] = False  # el radar tiene sus propios tests (sin internet)
    cfg["datos"]["carpeta"] = str(tmp_path / "datos")
    cfg["salida"]["carpeta"] = str(tmp_path / "res")
    v = serie_mercado(3000, 1, 0.2, t0=int(ahora * 1000) - 2000 * H)
    merc = MercadoFalso({("AAA/USDT:USDT", "1h"): v})
    llamadas = {"velas": 0, "ciclos": [], "datos": 0}
    original = merc.velas

    def velas(*a):
        llamadas["velas"] += 1
        return original(*a)
    merc.velas = velas
    t = {"ahora": ahora}
    liga, msgs, _ = liga_papel(tmp_path / "vivo", cfg, reloj=lambda: t["ahora"], mercado=merc)
    enviados = []

    def lanzar():
        p = Proceso()
        llamadas["ciclos"].append(p)
        return p

    def datos():
        llamadas["datos"] += 1
        return Hilo()
    s = Servicio(cfg, liga, merc, enviados.append, reloj=lambda: t["ahora"], lanzar_ciclo=lanzar, actualizar_datos=datos)
    return s, liga, t, llamadas, enviados


def _ts(texto):
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc).timestamp()


def test_procesa_cada_vela_una_sola_vez(tmp_path):
    s, liga, t, llamadas, _ = armar(tmp_path, _ts("2026-10-14T10:00:30"))
    liga.sincronizar_banco([registro(1)])
    liga.completar_titulares()
    s._velas()
    s._velas()
    assert llamadas["velas"] == 1
    t["ahora"] += 3600
    s._velas()
    assert llamadas["velas"] == 2 and liga.e["bots"]["bot1"]["ultima_vela_ts"] > 0


def test_agenda_diaria_noche_y_ciclos(tmp_path):
    s, liga, t, llamadas, enviados = armar(tmp_path, _ts("2026-10-14T02:00:00"))  # miércoles, 23:00 en Montevideo del día 13
    os.makedirs(os.path.join(s.cfg["datos"]["carpeta"], "velas"))
    open(os.path.join(s.cfg["datos"]["carpeta"], "velas", "AAAUSDT_1h.csv.gz"), "w").close()
    s.paso()
    assert llamadas["datos"] == 1 and liga.e["tareas"]["revision"] == "2026-10-14"
    assert llamadas["ciclos"] == []  # espera a que termine la descarga de datos
    assert any("Resumen del día" in m for m in enviados)  # ya son más de las 22 en Montevideo
    s.paso()  # terminó la descarga y el banco está vacío: primer ciclo
    assert llamadas["datos"] == 1 and len(llamadas["ciclos"]) == 1 and sum("Resumen" in m for m in enviados) == 1
    s.paso()
    assert len(llamadas["ciclos"]) == 1
    # termina el ciclo: lo nuevo del banco entra a la liga
    os.makedirs(os.path.join(s.cfg["salida"]["carpeta"], "banco"))
    with open(os.path.join(s.cfg["salida"]["carpeta"], "banco", "bot7.json"), "w") as f:
        json.dump(registro(7), f)
    llamadas["ciclos"][0].listo = True
    s.paso()
    assert "bot7" in liga.e["bots"] and liga.e["bots"]["bot7"]["rol"] == "titular"
    assert any("Se sumaron 1 suplente" in m for m in enviados)
    # el domingo a las 3 UTC arranca el ciclo semanal
    t["ahora"] = _ts("2026-10-18T03:05:00")
    s.paso()  # primero actualiza los datos del día...
    assert llamadas["datos"] == 2 and len(llamadas["ciclos"]) == 1
    s.paso()  # ...y después corre el ciclo semanal (misma semana que el primer ciclo, igual corre)
    assert len(llamadas["ciclos"]) == 2
    llamadas["ciclos"][1].listo = True
    s.paso()
    t["ahora"] += 3600
    s.paso()
    assert len(llamadas["ciclos"]) == 2  # una sola vez por semana


def test_comandos(tmp_path):
    s, liga, t, _, _ = armar(tmp_path, _ts("2026-10-14T10:00:00"))
    tg = Telegram("token", "123")
    respuestas = []
    tg.enviar = respuestas.append
    s.registrar_comandos(tg)

    def mandar(texto, chat=123):
        tg.procesar({"message": {"chat": {"id": chat}, "text": texto}})
        return respuestas[-1] if respuestas else ""

    assert "Prendido" in mandar("/estado") and "simulado" in mandar("/estado")
    assert "Pausado" in mandar("/pausar") and liga.e["pausado"]
    assert "Reanudado" in mandar("/reanudar") and not liga.e["pausado"]
    liga.e.update(apagado=True, motivo_apagado="la cuenta cayó 16%")
    assert "/reanudar confirmo" in mandar("/reanudar") and liga.e["apagado"]
    assert "Prendido de nuevo" in mandar("/reanudar confirmo") and not liga.e["apagado"]
    assert "Cerré todas" in mandar("/cerrar_todo") and liga.e["pausado"]
    assert "todavía no corrió" in mandar("/fabrica")
    assert "todavía no corrió" in mandar("/fábrica")  # con tilde también anda
    assert "apagado" in mandar("/radar")
    for c in ("/hoy", "/bots", "/informe", "/ayuda"):
        assert mandar(c)
    n = len(respuestas)
    mandar("/cerrar_todo", chat=999)  # chat ajeno: se ignora
    assert len(respuestas) == n


def _embudo(inventadas):
    from fabrica.filtros import FILTROS
    return {"inventadas": inventadas, "ya_examinadas_antes": 0, "candidatas": 0, **{c: 0 for c, _, _ in FILTROS}}


def test_al_prender_completa_datos_y_reintenta_un_primer_ciclo_vacio(tmp_path):
    s, liga, t, llamadas, enviados = armar(tmp_path, _ts("2026-10-15T05:00:00"))
    os.makedirs(os.path.join(s.cfg["datos"]["carpeta"], "velas"))
    open(os.path.join(s.cfg["datos"]["carpeta"], "velas", "AAAUSDT_1h.csv.gz"), "w").close()
    # estado guardado de antes: ya "bajó datos" hoy y ya hizo un primer ciclo ayer, pero no inventó nada
    liga.e["tareas"].update(datos="2026-10-15", primer_ciclo="2026-10-14")
    carpeta = os.path.join(s.cfg["salida"]["carpeta"], "ciclo_viejo")
    os.makedirs(carpeta)
    with open(os.path.join(carpeta, "embudo.json"), "w") as f:
        json.dump({"embudo": _embudo(0)}, f)
    with open(os.path.join(s.cfg["salida"]["carpeta"], "ultimo_ciclo.txt"), "w") as f:
        f.write("ciclo_viejo")
    s.paso()
    assert llamadas["datos"] == 1  # al prender completa los datos aunque "ya tocaba" hoy
    s.paso()
    assert len(llamadas["ciclos"]) == 1  # y reintenta el primer ciclo, que había salido vacío
    with open(os.path.join(carpeta, "embudo.json"), "w") as f:
        json.dump({"embudo": _embudo(5000)}, f)
    llamadas["ciclos"][0].listo = True
    s.paso()
    assert liga.e["tareas"]["primer_ciclo_ok"]
    t["ahora"] = _ts("2026-10-16T05:00:00")
    s.paso()
    s.paso()
    assert len(llamadas["ciclos"]) == 1 and llamadas["datos"] == 2  # ya salió bien: no se repite


def test_comando_ciclo(tmp_path):
    s, liga, t, llamadas, _ = armar(tmp_path, _ts("2026-10-15T05:00:00"))
    assert "no hay datos" in s.cmd_ciclo()
    os.makedirs(os.path.join(s.cfg["datos"]["carpeta"], "velas"))
    open(os.path.join(s.cfg["datos"]["carpeta"], "velas", "AAAUSDT_1h.csv.gz"), "w").close()
    assert "arrancó" in s.cmd_ciclo() and len(llamadas["ciclos"]) == 1
    assert "Ya hay un ciclo" in s.cmd_ciclo() and len(llamadas["ciclos"]) == 1


def test_chequeo_de_salud_avisa_despues_de_bajar_datos(tmp_path):
    s, liga, t, llamadas, enviados = armar(tmp_path, _ts("2026-10-15T05:00:00"))
    s.paso()  # baja datos (no hay ninguno todavía)
    s.paso()  # terminó la descarga: chequeo, y como no hay datos, avisa
    assert any("Chequeo de salud" in m and "no hay datos" in m for m in enviados)
    assert "Chequeo de salud" in s.chequeo_salud()


def test_avisa_enseguida_si_el_ciclo_sale_vacio_o_se_corta(tmp_path):
    s, liga, t, llamadas, enviados = armar(tmp_path, _ts("2026-10-15T05:00:00"))
    carpeta = os.path.join(s.cfg["salida"]["carpeta"], "ciclo_20261015_050000")
    os.makedirs(carpeta)
    with open(os.path.join(carpeta, "embudo.json"), "w") as f:
        json.dump({"embudo": _embudo(0), "por_mercado": [
            {"simbolo": "BTC/USDT:USDT", "tf": "1h", "error": "pocos datos (1000 velas)"},
            {"simbolo": "ETH/USDT:USDT", "tf": "4h", "error": None}]}, f)
    with open(os.path.join(s.cfg["salida"]["carpeta"], "ultimo_ciclo.txt"), "w") as f:
        f.write("ciclo_20261015_050000")
    s.ciclo_en_curso = Proceso()
    s._al_terminar_ciclo()
    aviso = [m for m in enviados if "NINGUNA estrategia" in m]
    assert aviso and "BTC 1h: pocos datos (1000 velas)" in aviso[0] and "ETH" not in aviso[0]
    assert not liga.e["tareas"].get("primer_ciclo_ok")
    # un ciclo que se corta con error no se presenta como resultado
    p = Proceso()
    p.returncode = 1
    s.ciclo_en_curso = p
    n = len(enviados)
    s._al_terminar_ciclo()
    assert len(enviados) == n + 1 and "se cortó con un error" in enviados[-1]
