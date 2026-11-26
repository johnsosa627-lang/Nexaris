"""Siembra el estado del desafío de fondeo con el equipo ya entrenado de otra cuenta.

Uso único (one-shot), con el servicio APAGADO para que no pise el archivo:
    python -m fabrica.sembrar_fondeo
o leyéndolo por stdin dentro de un contenedor con el volumen /data montado.

Copia el equipo (titulares + suplentes + su experiencia) del estado de ORIGEN al estado
del DESAFÍO, pero resetea la cuenta al capital del desafío y arranca plano (sin posiciones
heredadas ni plata real de otra cuenta). No baja exigencias ni toca estrategias.

Rutas y capital por variables de entorno (con valores por defecto):
    SRC_ESTADO=/data/vivo/estado_liga.json
    DST_ESTADO=/data/vivo-fondeo/estado_liga.json
    CAP_FONDEO=5000
"""
import json
import os


def sembrar(src: str, dst: str, capital: float) -> dict:
    e = json.load(open(src, encoding="utf-8"))
    # Cuenta fresca en el capital del desafío
    e["cuenta"] = {"equity": capital, "pico": capital, "dia": "", "inicio_dia": capital,
                   "pnl_hoy": 0.0, "racha_hoy": 0, "freno_dia": ""}
    # Arrancar plano: sin posiciones heredadas (no existen en el exchange del desafío)
    for b in e.get("bots", {}).values():
        b["posicion"] = None
    # Nada de plata real de otra cuenta en el desafío
    e.pop("cuenta_real", None)
    e["pausado"] = False
    e["apagado"] = False
    e["motivo_apagado"] = ""
    e["real_confirmado"] = False
    e["eventos"] = []

    d = os.path.dirname(dst)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(e, f, ensure_ascii=False)
    return e


def main() -> None:
    src = os.environ.get("SRC_ESTADO", "/data/vivo/estado_liga.json")
    dst = os.environ.get("DST_ESTADO", "/data/vivo-fondeo/estado_liga.json")
    cap = float(os.environ.get("CAP_FONDEO", "5000"))
    e = sembrar(src, dst, cap)
    b = list(e["bots"].values())
    print("OK -> titulares:", sum(1 for x in b if x["rol"] == "titular"),
          "| suplentes:", sum(1 for x in b if x["rol"] == "suplente"),
          "| equity:", e["cuenta"]["equity"],
          "| posiciones abiertas:", sum(1 for x in b if x.get("posicion")))


if __name__ == "__main__":
    main()
