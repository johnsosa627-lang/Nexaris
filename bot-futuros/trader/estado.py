"""Estado persistente en JSON (escritura atómica) dentro del volumen."""
import copy
import json
import os
import threading

ESTADO_INICIAL = {
    "pausado": False,
    "apagado": False,
    "motivo_apagado": "",
    "posicion": None,          # dict con lado, cantidad, entrada, sl, tp, abierta_ts, abierta_iso
    "dia": "",                 # día UTC en curso (YYYY-MM-DD)
    "saldo_inicio_dia": None,
    "operaciones_hoy": 0,
    "corte_dia": "",           # día UTC en que se activó el corte por pérdida
    "ultima_vela_ts": 0,
    "ia": {"dia": "", "llamadas_dia": 0, "semana": "", "llamadas_semana": 0},
    "papel": {"saldo": None, "posicion": None},
}


class Estado:
    def __init__(self, ruta: str):
        self.ruta = ruta
        self._lock = threading.RLock()
        self.datos = copy.deepcopy(ESTADO_INICIAL)
        self._cargar()

    def _cargar(self):
        if not os.path.exists(self.ruta):
            return
        with open(self.ruta, "r", encoding="utf-8") as f:
            guardado = json.load(f)
        for clave, valor in guardado.items():
            if isinstance(valor, dict) and isinstance(self.datos.get(clave), dict):
                self.datos[clave].update(valor)
            else:
                self.datos[clave] = valor

    def guardar(self):
        with self._lock:
            directorio = os.path.dirname(self.ruta) or "."
            os.makedirs(directorio, exist_ok=True)
            temporal = self.ruta + ".tmp"
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, indent=2, ensure_ascii=False)
            os.replace(temporal, self.ruta)

    def __getitem__(self, clave):
        return self.datos[clave]

    def __setitem__(self, clave, valor):
        with self._lock:
            self.datos[clave] = valor
            self.guardar()

    def actualizar(self, **cambios):
        with self._lock:
            self.datos.update(cambios)
            self.guardar()
