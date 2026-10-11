"""Punto de entrada: arma los componentes y corre el ciclo cada INTERVALO_VIGILANCIA segundos."""
import os
import time

from .bot import Bot
from .broker import BrokerBinance, BrokerPapel, crear_cliente
from .config import Config
from .estado import Estado
from .ia import FiltroIA
from .registro import RegistroOperaciones, configurar_log
from .telegram_bot import Telegram


def construir(cfg: Config):
    estado = Estado(os.path.join(cfg.data_dir, f"estado_{cfg.modo}.json"))
    cliente = crear_cliente(cfg)
    broker = BrokerPapel(cfg, cliente, estado) if cfg.modo == "papel" else BrokerBinance(cfg, cliente)
    telegram = Telegram(cfg.telegram_token, cfg.telegram_chat_id)
    bot = Bot(cfg, broker, estado, FiltroIA(cfg, estado),
              RegistroOperaciones(os.path.join(cfg.data_dir, "operaciones.csv")), telegram.enviar)
    for comando, funcion in {
        "/estado": bot.cmd_estado, "/pausar": bot.cmd_pausar, "/reanudar": bot.cmd_reanudar,
        "/cerrar": bot.cmd_cerrar, "/operaciones": bot.cmd_operaciones, "/reactivar": bot.cmd_reactivar,
        "/ayuda": bot.cmd_ayuda, "/start": bot.cmd_ayuda,
    }.items():
        telegram.registrar(comando, funcion)
    return bot, telegram


def main():
    cfg = Config.desde_entorno()
    log = configurar_log(cfg.data_dir)
    log.info("Iniciando bot en modo %s (%s %s)", cfg.modo, cfg.simbolo, cfg.timeframe)
    if cfg.modo in ("testnet", "real") and not (cfg.binance_api_key and cfg.binance_api_secret):
        raise SystemExit("Faltan BINANCE_API_KEY / BINANCE_API_SECRET para el modo " + cfg.modo)
    bot, telegram = construir(cfg)
    telegram.iniciar()

    # El arranque puede fallar por red: reintentar sin operar hasta lograrlo
    espera = 10
    while True:
        try:
            bot.iniciar()
            break
        except Exception as e:  # noqa: BLE001
            log.exception("Fallo al iniciar")
            bot.avisar_error(f"no pude iniciar ({e}). Reintento en {espera}s.")
            time.sleep(espera)
            espera = min(espera * 2, 300)

    while True:
        inicio = time.time()
        try:
            bot.ciclo()
        except Exception as e:  # noqa: BLE001
            log.exception("Error en el ciclo")
            bot.avisar_error(str(e)[:500])
        time.sleep(max(1.0, cfg.intervalo_vigilancia - (time.time() - inicio)))


if __name__ == "__main__":
    main()
