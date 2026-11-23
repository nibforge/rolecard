"""Local log file in the user's data folder (never sent anywhere)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = "rolecard.log"
_MARK = "_rolecard_file"


def init_logging(data_dir: Path) -> None:
    """Send the ``rolecard`` loggers (WARNING and up) to ``<data_dir>/rolecard.log``."""
    logger = logging.getLogger("rolecard")
    for handler in [h for h in logger.handlers if getattr(h, _MARK, False)]:
        logger.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(data_dir / LOG_FILE, maxBytes=1_000_000, backupCount=2,
                                  encoding="utf-8", delay=True)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    setattr(handler, _MARK, True)
    logger.addHandler(handler)
