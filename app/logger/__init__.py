import inspect
import logging.handlers
import os
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "gestpro.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class ClassNameFilter(logging.Filter):
    def filter(self, record):
        abs_path = os.path.abspath(record.pathname)
        # normalizza gli slash così funziona su zip/pex, linux e windows
        norm = abs_path.replace("\\", "/")

        # prova a tagliare a partire da "app/"
        idx = norm.rfind("/app/")
        if idx != -1:
            rel = norm[idx + len("/app/"):]
        else:
            # fallback: solo il filename
            rel = os.path.basename(norm)

        if rel.endswith(".py"):
            rel = rel[:-3]

        # per sicurezza, converti in notazione a punti
        record.relpath = "app." + rel.replace("/", ".")

        # --- classe chiamante (come già facevi) ---
        record.classname = ""
        frame = inspect.currentframe()
        while frame:
            code = frame.f_code
            if code.co_name == record.funcName:
                self_obj = frame.f_locals.get("self")
                if self_obj:
                    record.classname = self_obj.__class__.__name__
                    break
            frame = frame.f_back
        return True


class SmartClassFormatter(logging.Formatter):
    def format(self, record):
        if record.classname:
            record.classname = f"{record.classname}"
        return super().format(record)


handler = logging.handlers.TimedRotatingFileHandler(
    LOG_FILE, when="midnight", interval=1, backupCount=5, encoding="utf-8"
)
console = logging.StreamHandler()

fmt = "%(asctime)s - [%(levelname)s] - %(relpath)s.%(classname)s.%(funcName)s(): %(message)s {%(lineno)d}"
formatter = SmartClassFormatter(fmt)

handler.setFormatter(formatter)
console.setFormatter(formatter)

logger = logging.getLogger("GestPro")
logger.setLevel(os.getenv("LOG_LEVEL", "DEBUG").upper())
logger.addFilter(ClassNameFilter())
logger.addHandler(handler)
logger.addHandler(console)
logger.propagate = False
