import json
import asyncio
import redis.asyncio as redis
import time
import logging
import rx
from rx import create

logger = logging.getLogger("main")

log_hearbeats = True

class RxRedis:
    def __init__(self,hostname,namespace, port, event_name="galcom.bridge_message"):
        self.hostname = hostname
        self.namespace = namespace
        self.port = port
        self.room = None
        self.event_name = event_name
        self.server = None
        self.pubsub = None
        self.loop = asyncio.get_event_loop()
        self.failure_count=0
        self.connecting = False


    async def connect(self):
        if self.connecting:
            logger.debug("already connecting to redis")
            return self.server is not None and self.pubsub is not None

        try:
            self.connecting = True
            logger.debug(f"connecting to redis at {self.hostname}:{self.port}...")
            self.server = await redis.from_url(f"redis://{self.hostname}",port=int(self.port),db=0)
            self.pubsub = self.server.pubsub()
            await self.pubsub.subscribe("events")
            self.failure_count = 0
            logger.debug(f"connected to redis. listening with room {self.room} and event name {self.event_name}")
            return True
        except Exception as e:
            logger.warning(f"unable to connect to redis at {self.hostname}:{self.port}: {e}")
            if "HTTP/1.1" in str(e):
                logger.warning("redis endpoint returned HTTP response; verify redis_hostname/redis_port")
            self.server = None
            self.pubsub = None
            return False
        finally:
            self.connecting = False

    async def redis_observer(self,observer,scheduler):
        logger.debug("starting redis observer")

        while True:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True,timeout=30*60) #timeout 30min
                #logger.debug(f"got raw message from redis: {message}")
                if message and "data" in message:
                    data = json.loads(message["data"])
                    # field "room" has format "<hostname>:room:<room name>"
                    if data and data.get("event") == self.event_name and  data.get("room") == self.room:
                        #logger.debug(f"<--Redis filtered RAW {message}")
                        match data["message"]:
                            case {"type":"heartbeat"} if log_hearbeats:
                                logger.debug(f"<--Redis {data['message']}")
                            case _:
                                logger.info(f"<--Redis {data['message']}")
                        observer.on_next(data['message'])
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.exception(f"caught error while reading redis messages")
                self.failure_count += 1
                await asyncio.sleep(5)

                #try re-connecting after 10 errors
                if self.failure_count > 10:
                    self.failure_count = 0
                    logger.warning("re-connecting to Redis")
                    if not await self.connect():
                        logger.warning("redis reconnect attempt failed")

    async def force_reconnect(self):
        if self.connecting:
            logger.debug("already connecting, not forcing redis reconnect")
            return

        logger.info("forcing redis reconnect")
        await self.connect()


    def subscribe_doc(self, doctype, docname):
        self.room = f"doc:{doctype}/{docname}"
    def set_room(self,room):
        self.room = room

    def create_observable(self):
        return create(lambda o,s:asyncio.create_task(self.redis_observer(o,s)))

    async def send_message(self,event,message,room):
        match message:
            case "heartbeat_ack" if log_hearbeats:
                logger.debug(f"-->Redis {event}, {room}, {message}")
            case _:
                logger.info(f"-->Redis {event}, {room}, {message}")

        await self.server.publish(
            "events",
            json.dumps({
                "event":event,
                "message":message,
                "namespace":self.namespace,
                "room":room
            })
        )
