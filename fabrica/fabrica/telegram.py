"""Telegram: el control remoto. Solo obedece al chat configurado en TELEGRAM_CHAT_ID."""
from __future__ import annotations

import logging
import threading
import time

import requests

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = str(chat_id)
        self.activo = bool(token and chat_id)
        self._offset = None
        self.comandos: dict = {}

    def _url(self, metodo: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{metodo}"

    def enviar(self, texto: str) -> None:
        if not self.activo:
            log.info("[telegram desactivado] %s", texto)
            return
        for parte in [texto[i:i + 3900] for i in range(0, len(texto), 3900)] or [""]:
            try:
                requests.post(self._url("sendMessage"), json={"chat_id": self.chat_id, "text": parte},
                              timeout=20)
            except Exception as ex:  # nunca dejar que Telegram tire abajo el sistema
                log.warning("no se pudo enviar a Telegram: %s", type(ex).__name__)

    def _descartar_viejos(self) -> None:
        """Los mensajes que llegaron mientras el sistema estaba apagado se ignoran."""
        try:
            r = requests.get(self._url("getUpdates"), params={"timeout": 0}, timeout=20).json()
            ups = r.get("result", [])
            if ups:
                self._offset = ups[-1]["update_id"] + 1
        except Exception:
            pass

    def escuchar(self) -> None:
        if not self.activo:
            return
        self._descartar_viejos()
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self) -> None:
        while True:
            try:
                params = {"timeout": 50}
                if self._offset is not None:
                    params["offset"] = self._offset
                r = requests.get(self._url("getUpdates"), params=params, timeout=60).json()
                for u in r.get("result", []):
                    self._offset = u["update_id"] + 1
                    msg = u.get("message") or {}
                    if str(msg.get("chat", {}).get("id")) != self.chat_id:
                        continue  # no es el dueño: se ignora
                    texto = (msg.get("text") or "").strip()
                    if not texto.startswith("/"):
                        continue
                    cmd = texto.split()[0].split("@")[0].lower()
                    fn = self.comandos.get(cmd) or self.comandos.get("/ayuda")
                    try:
                        self.enviar(fn())
                    except Exception as ex:
                        log.exception("error en comando %s", cmd)
                        self.enviar(f"Uy, hubo un error con {cmd}: {type(ex).__name__}")
            except Exception:
                time.sleep(10)
