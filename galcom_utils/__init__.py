import logging
from .logging_setup import get_and_config_logger, update_loki_tags
from .RxRedis import RxRedis
from .RxWebsocket import RxWebsocket
from .RxSerial import RxSerial, SerialData, ParseError, SerialCrash

logger = logging.getLogger("main")


async def connect(config, docname, doctype="Compass Workstation", event_name="galcom.bridge_message"):
	redis_host = config.get("redis_hostname", config["hostname"])
	redis_port = config.get("redis_port", "6379")

	redis_socket = RxRedis(
		redis_host,
		config["sitename"],
		redis_port,
		event_name=event_name,
	)
	redis_socket.subscribe_doc(doctype, docname)
	redis_connected = await redis_socket.connect()
	if redis_connected:
		logger.info(
			f"using Redis event stream with room {redis_socket.room} on {redis_host}:{redis_port}"
		)
		return redis_socket
	logger.warning("Redis connection failed. Falling back to websocket")

	websocket = RxWebsocket(
		config["hostname"],
		config["sitename"],
		config["websocket_port"],
		config["key"],
		config["secret"],
		event_name=event_name,
	)
	await websocket.connect(config["erp_port"])
	await websocket.subscribe_doc(doctype, docname)
	return websocket


__all__ = [
	"get_and_config_logger",
	"update_loki_tags",
	"RxRedis",
	"RxWebsocket",
	"RxSerial",
	"SerialData",
	"ParseError",
	"SerialCrash",
	"connect",
]
