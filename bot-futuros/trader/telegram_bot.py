"""Control por Telegram (long polling). Solo responde al TELEGRAM_CHAT_ID configurado."""
import logging
import threading
import time

import requests

log = logging.getLogger("trader")


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = str(chat_id).strip()
        self.url = f"https://api.telegram.org/bot{token}"
        self.comandos = {}
        self._offset = None

    @property
    def activo(self) -> bool:
        return bool(self.token and self.chat_id)

    def enviar(self, texto: str):
        log.info("[TG] %s", texto.replace("\n", " | "))
        if not self.activo:
            return
        for intento in range(3):
            try:
                r = requests.post(f"{self.url}/sendMessage",
                                  json={"chat_id": self.chat_id, "text": texto[:4000]}, timeout=15)
                if r.status_code == 200:
                    return
                log.warning("Telegram respondió %s: %s", r.status_code, r.text[:200])
            except Exception as e:  # noqa: BLE001
                log.warning("No se pudo enviar a Telegram: %s", e)
            time.sleep(2 * (intento + 1))

    def registrar(self, comando: str, funcion):
        self.comandos[comando] = funcion

    def _descartar_pendientes(self):
        """Ignora comandos viejos acumulados mientras el bot estaba apagado (ej: un /cerrar)."""
        try:
            r = requests.get(f"{self.url}/getUpdates", params={"offset": -1, "timeout": 0}, timeout=15)
            resultados = r.json().get("result", [])
            if resultados:
                self._offset = resultados[-1]["update_id"] + 1
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram: no se pudieron descartar pendientes: %s", e)

    def procesar(self, update: dict):
        mensaje = update.get("message") or update.get("edited_message") or {}
        chat = str((mensaje.get("chat") or {}).get("id", ""))
        texto = (mensaje.get("text") or "").strip()
        if not texto:
            return
        if chat != self.chat_id:
            log.warning("Telegram: mensaje ignorado de chat no autorizado %s", chat)
            return
        comando = texto.split()[0].split("@")[0].lower()
        funcion = self.comandos.get(comando)
        if not funcion:
            self.enviar("Comandos: /estado /pausar /reanudar /cerrar /operaciones /reactivar /ayuda")
            return
        try:
            respuesta = funcion()
        except Exception as e:  # noqa: BLE001
            log.exception("Error en comando %s", comando)
            respuesta = f"⚠️ Error ejecutando {comando}: {e}"
        if respuesta:
            self.enviar(respuesta)

    def _bucle(self):
        self._descartar_pendientes()
        while True:
            try:
                params = {"timeout": 25}
                if self._offset is not None:
                    params["offset"] = self._offset
                r = requests.get(f"{self.url}/getUpdates", params=params, timeout=35)
                for update in r.json().get("result", []):
                    self._offset = update["update_id"] + 1
                    self.procesar(update)
            except Exception as e:  # noqa: BLE001
                log.warning("Telegram polling: %s", e)
                time.sleep(5)

    def iniciar(self):
        if not self.activo:
            log.warning("Telegram desactivado: faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
            return
        threading.Thread(target=self._bucle, name="telegram", daemon=True).start()
