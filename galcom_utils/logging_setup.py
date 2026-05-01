import logging
import socket
from multiprocessing import Queue
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import logging_loki

_loki_tags = None
LOKI_URL = "http://192.168.0.192:3100/loki/api/v1/push"


def _is_loki_url_reachable(url, timeout=2):
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout):
            return True
    except HTTPError:
        # Non-2xx still proves the endpoint is reachable.
        return True
    except (URLError, TimeoutError, OSError):
        return False


def get_and_config_logger(name):
    logger = logging.getLogger("main")

    if not logger.hasHandlers():
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(module)s] %(message)s")
        logger.setLevel(logging.DEBUG)
        add_loki_logger(name, logger, formatter)
        add_console_logger(logger, formatter)

    return logger


def update_loki_tags(bridge_id):
    global _loki_tags
    if _loki_tags is not None:
        _loki_tags["bridge_id"] = bridge_id


def add_loki_logger(name, logger, formatter):
    global _loki_tags

    for handler in logger.handlers:
        if type(handler) is logging_loki.LokiQueueHandler:
            return

    _loki_tags = {
        "application": name,
        "hostname": socket.gethostname(),
        "bridge_id": "unset",
    }

    if not _is_loki_url_reachable(LOKI_URL):
        print("not adding loki logger since endpoint is not reachable")
        return

    loki_handler = logging_loki.LokiQueueHandler(
        Queue(-1),
        url=LOKI_URL,
        tags=_loki_tags,
        version="1",
    )
    loki_handler.setFormatter(formatter)
    logger.addHandler(loki_handler)


def add_console_logger(logger, formatter):
    for handler in logger.handlers:
        if type(handler) is logging.StreamHandler:
            return

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
