"""Configuración leída 100% desde variables de entorno."""
import os
from dataclasses import dataclass

APALANCAMIENTO_MAXIMO = 3
MODOS_VALIDOS = ("papel", "testnet", "real")


def _env(nombre: str, defecto: str = "") -> str:
    valor = os.getenv(nombre)
    if valor is None or valor.strip() == "":
        return defecto
    return valor.strip()


def _float(nombre: str, defecto: float) -> float:
    return float(_env(nombre, str(defecto)).replace(",", "."))


def _int(nombre: str, defecto: int) -> int:
    return int(float(_env(nombre, str(defecto))))


@dataclass(frozen=True)
class Config:
    modo: str = "papel"
    confirmar_real: bool = False

    simbolo: str = "XRP/USDT:USDT"
    timeframe: str = "15m"

    apalancamiento: int = 3
    fraccion_margen: float = 0.90
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 6.0
    max_operaciones_dia: int = 5
    perdida_max_dia_pct: float = 20.0
    saldo_minimo: float = 10.0
    intervalo_vigilancia: int = 30

    saldo_inicial_papel: float = 15.0
    comision_pct: float = 0.05

    ia_modelo: str = "nex-agi/nex-n2.5-pro:free"
    ia_modelo_respaldo: str = "nex-agi/nex-n2.5-mini"
    ia_score_minimo: int = 60
    ia_max_dia: int = 20
    ia_max_semana: int = 80
    ia_velas: int = 20
    ia_timeout: int = 60

    binance_api_key: str = ""
    binance_api_secret: str = ""
    openrouter_api_key: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""

    data_dir: str = "/data"

    @classmethod
    def desde_entorno(cls) -> "Config":
        modo = _env("MODO", "papel").lower()
        if modo not in MODOS_VALIDOS:
            raise ValueError(f"MODO inválido '{modo}'. Usá: {', '.join(MODOS_VALIDOS)}")
        apalancamiento = _int("APALANCAMIENTO", 3)
        # Tope duro: nunca más de 3x, aunque la variable diga otra cosa
        apalancamiento = max(1, min(apalancamiento, APALANCAMIENTO_MAXIMO))
        fraccion = _float("PORCENTAJE_MARGEN", 90.0) / 100.0
        fraccion = max(0.01, min(fraccion, 0.95))
        return cls(
            modo=modo,
            confirmar_real=_env("CONFIRMAR_REAL", "NO").upper() == "SI",
            simbolo=_env("SIMBOLO", "XRP/USDT:USDT"),
            timeframe=_env("TIMEFRAME", "15m"),
            apalancamiento=apalancamiento,
            fraccion_margen=fraccion,
            stop_loss_pct=_float("STOP_LOSS_PCT", 3.0),
            take_profit_pct=_float("TAKE_PROFIT_PCT", 6.0),
            max_operaciones_dia=_int("MAX_OPERACIONES_DIA", 5),
            perdida_max_dia_pct=_float("PERDIDA_MAX_DIA_PCT", 20.0),
            saldo_minimo=_float("SALDO_MINIMO", 10.0),
            intervalo_vigilancia=max(5, _int("INTERVALO_VIGILANCIA", 30)),
            saldo_inicial_papel=_float("SALDO_INICIAL_PAPEL", 15.0),
            comision_pct=_float("COMISION_PCT", 0.05),
            ia_modelo=_env("IA_MODELO", "nex-agi/nex-n2.5-pro:free"),
            ia_modelo_respaldo=_env("IA_MODELO_RESPALDO", "nex-agi/nex-n2.5-mini"),
            ia_score_minimo=_int("IA_SCORE_MINIMO", 60),
            ia_max_dia=_int("IA_MAX_LLAMADAS_DIA", 20),
            ia_max_semana=_int("IA_MAX_LLAMADAS_SEMANA", 80),
            ia_velas=_int("IA_VELAS", 20),
            ia_timeout=_int("IA_TIMEOUT", 60),
            binance_api_key=_env("BINANCE_API_KEY"),
            binance_api_secret=_env("BINANCE_API_SECRET"),
            openrouter_api_key=_env("OPENROUTER_API_KEY"),
            telegram_token=_env("TELEGRAM_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            data_dir=_env("DATA_DIR", "/data"),
        )
