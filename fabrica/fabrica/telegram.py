"""Telegram: comandos en español y avisos. Solo responde al TELEGRAM_CHAT_ID configurado."""
import difflib
import logging
import re
import unicodedata
import threading
import time

import requests

log = logging.getLogger("fabrica")


TOKEN = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{35}")


def limpiar_token(valor: str) -> str:
    """El token del bot tiene la forma 123456789:<35 caracteres>. Si al pegarlo quedó texto de más
    (por ejemplo "TELEGRAM_TOKEN=" repetido, antes o después), me quedo solo con el token."""
    valor = (valor or "").strip()
    m = TOKEN.search(valor)
    return m.group(0) if m else valor.rsplit("=", 1)[-1].strip()


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token or ""
        self.chat_id = str(chat_id or "").strip()
        self.url = f"https://api.telegram.org/bot{self.token}"
        self.comandos = {}
        self._offset = None

    @property
    def activo(self) -> bool:
        return bool(self.token and self.chat_id)

    def enviar(self, texto: str):
        log.info("[Telegram] %s", texto.replace("\n", " | ")[:500])
        if not self.activo:
            return
        for parte in [texto[i:i + 3900] for i in range(0, len(texto), 3900)] or [""]:
            for intento in range(3):
                try:
                    r = requests.post(f"{self.url}/sendMessage", json={"chat_id": self.chat_id, "text": parte}, timeout=15)
                    if r.status_code == 200:
                        break
                    log.warning("Telegram respondió %s: %s", r.status_code, r.text[:200])
                except Exception as e:  # noqa: BLE001
                    log.warning("No se pudo enviar a Telegram: %s", e)
                time.sleep(2 * (intento + 1))

    def registrar(self, comando: str, funcion):
        """`funcion(argumentos: str) -> str` con la respuesta."""
        self.comandos[comando] = funcion

    def procesar(self, update: dict):
        mensaje = update.get("message") or update.get("edited_message") or {}
        chat = str((mensaje.get("chat") or {}).get("id", ""))
        texto = (mensaje.get("text") or "").strip()
        if not texto:
            return
        if chat != self.chat_id:
            log.warning("Telegram: mensaje ignorado de un chat no autorizado (%s)", chat)
            return
        partes = texto.split(maxsplit=1)
        # sin tildes: el teclado del celular a veces escribe "/diagnóstico" o "/fábrica"
        comando = unicodedata.normalize("NFKD", partes[0].split("@")[0].lower()).encode("ascii", "ignore").decode()
        argumentos = partes[1].strip().lower() if len(partes) > 1 else ""
        funcion = self.comandos.get(comando)
        if not funcion:
            # error de tipeo ("/clico"): si se parece mucho a un comando, sugerirlo
            parecido = difflib.get_close_matches(comando, list(self.comandos), n=1, cutoff=0.6)
            respuesta = (f"¿Quisiste decir {parecido[0]}? Tocalo para mandarlo.\n\n" if parecido else "") + \
                "Comandos: " + " ".join(sorted(self.comandos))
        else:
            try:
                respuesta = funcion(argumentos)
            except Exception as e:  # noqa: BLE001
                log.exception("Error en el comando %s", comando)
                respuesta = f"⚠️ Error con {comando}: {e}"
        if respuesta:
            self.enviar(respuesta)

    def _descartar_pendientes(self):
        """Ignora comandos viejos acumulados mientras el servicio estaba apagado (ej: un /cerrar_todo)."""
        try:
            r = requests.get(f"{self.url}/getUpdates", params={"offset": -1, "timeout": 0}, timeout=15)
            res = r.json().get("result", [])
            if res:
                self._offset = res[-1]["update_id"] + 1
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram: %s", e)

    def _bucle(self):
        self._descartar_pendientes()
        while True:
            try:
                params = {"timeout": 25}
                if self._offset is not None:
                    params["offset"] = self._offset
                r = requests.get(f"{self.url}/getUpdates", params=params, timeout=35)
                datos = r.json()
                if not datos.get("ok"):  # token mal puesto u otro problema: avisar en vez de girar en vacío
                    log.warning("Telegram no acepta el token (%s): %s", r.status_code, str(datos.get("description"))[:200])
                    time.sleep(60)
                    continue
                for update in datos.get("result", []):
                    self._offset = update["update_id"] + 1
                    self.procesar(update)
            except Exception as e:  # noqa: BLE001
                log.warning("Telegram: %s", e)
                time.sleep(5)

    def iniciar(self):
        if not self.activo:
            log.warning("Telegram desactivado: faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
            return
        threading.Thread(target=self._bucle, name="telegram", daemon=True).start()
