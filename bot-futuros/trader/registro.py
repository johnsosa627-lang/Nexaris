"""Log de eventos a archivo y registro de operaciones en CSV."""
import csv
import logging
import os
from logging.handlers import RotatingFileHandler

COLUMNAS_CSV = ["fecha", "fecha_apertura", "modo", "simbolo", "lado", "entrada", "salida",
                "cantidad", "resultado_usdt", "motivo_cierre"]


def configurar_log(data_dir: str) -> logging.Logger:
    os.makedirs(data_dir, exist_ok=True)
    log = logging.getLogger("trader")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    archivo = RotatingFileHandler(os.path.join(data_dir, "eventos.log"), maxBytes=2_000_000,
                                  backupCount=5, encoding="utf-8")
    archivo.setFormatter(formato)
    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    log.addHandler(archivo)
    log.addHandler(consola)
    return log


class RegistroOperaciones:
    def __init__(self, ruta_csv: str):
        self.ruta = ruta_csv

    def guardar(self, fila: dict):
        nuevo = not os.path.exists(self.ruta)
        os.makedirs(os.path.dirname(self.ruta) or ".", exist_ok=True)
        with open(self.ruta, "a", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUMNAS_CSV)
            if nuevo:
                escritor.writeheader()
            escritor.writerow({c: fila.get(c, "") for c in COLUMNAS_CSV})

    def leer(self, modo: str = None) -> list:
        if not os.path.exists(self.ruta):
            return []
        with open(self.ruta, newline="", encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        if modo:
            filas = [f for f in filas if f.get("modo") == modo]
        return filas

    def ultimas(self, n: int = 10, modo: str = None) -> list:
        return self.leer(modo)[-n:]

    def resumen(self, modo: str, dia: str) -> dict:
        filas = self.leer(modo)
        total = sum(float(f["resultado_usdt"]) for f in filas)
        hoy = [f for f in filas if f["fecha"].startswith(dia)]
        return {
            "total": total,
            "operaciones_total": len(filas),
            "hoy": sum(float(f["resultado_usdt"]) for f in hoy),
            "operaciones_hoy": len(hoy),
            "ganadas": sum(1 for f in filas if float(f["resultado_usdt"]) > 0),
        }
