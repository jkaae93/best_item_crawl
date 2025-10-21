from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path


LOG_ROOT = Path("outputs/logs")


def setup_logging(app_name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Initialize a named logger that writes to outputs/logs and stdout.

    - File name format: outputs/logs/{app_name}_YYYYMMDD_HHMMSS.log
    - Avoids duplicate handlers if called multiple times
    """
    logger = logging.getLogger(app_name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = LOG_ROOT / f"{app_name}_{ts}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False

    return logger


def install_global_exception_logger(logger: logging.Logger) -> None:
    """
    Route uncaught exceptions to the provided logger (main thread and other threads).
    KeyboardInterrupt keeps default behavior.
    """

    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _handle_exception

    # Python 3.8+ thread exception hook
    if hasattr(threading, "excepthook"):
        def _thread_excepthook(args):  # type: ignore[no-redef]
            if issubclass(args.exc_type, KeyboardInterrupt):
                return
            logger.error(
                "Unhandled exception in thread",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = _thread_excepthook  # type: ignore[attr-defined]
