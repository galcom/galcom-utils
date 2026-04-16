import asyncio
import logging
import sys
from rx import create
import socketio

logger = logging.getLogger("main")
debug=False

class RxWebsocket:
    def __init__(self,hostname,namespace, port,key, secret, event_name="galcom.bridge_message"):
        self.hostname = hostname
        self.namespace=namespace
        self.port = port
        self.key=key
        self.secret = secret
        self.event_name = event_name
        self.server = None
        self.loop = asyncio.get_event_loop()
        self.connection_count=0
        self.observer=None
        self.connecting = False
        self._doctype = None
        self._docname = None


    #server_port should be http/https port, which can be different than the websocket port
    async def connect(self,server_port):
        try:
            logger.debug(f"connecting to websocket at {self.hostname}:{self.port}, namespace {self.namespace} ...")
            self.connection_count=0
            self.server_port = server_port

            protocol = "wss" if int(self.port) == 443 else "ws"
            self.server= socketio.AsyncClient(logger=debug,engineio_logger=debug)

            def get_headers():
                logger.debug("getting headers for websocket connection")
                return {
                        "Origin":f"{self.hostname}:{self.server_port}",
                        'Authorization': f"token {self.key}:{self.secret}",
                        "Cookie":"dummy=novalue"
                }

            await self.server.connect(f"{protocol}://{self.hostname}:{self.port}",
                                      namespaces=[f"/{self.namespace}"],
                                      headers=get_headers)
            logger.debug(f"socketio connected. sid: {self.server.sid}, {self.server.transport}")

            if self._doctype is not None:
                await self.server.emit("doc_subscribe", (self._doctype, self._docname), namespace=f"/{self.namespace}")

            self.server.on(self.event_name, self.message_handler, namespace=f"/{self.namespace}")

            self.server.on("connect", self.on_connect, namespace=f"/{self.namespace}")
            self.server.on("disconnect", self.on_disconnect, namespace=f"/{self.namespace}")

            self.connection_count = 1

        except Exception as e:
            logger.exception(f"caught error in init {e}")


    def message_handler(self,message,arg2=None):
        logger.debug(f"got websocket message: {message}, arg2: {arg2}")
        logger.debug(f"connection count {self.connection_count}")
        if self.observer:
            try:
                logger.info(f"<--WS {message}")
                self.observer.on_next(message)
            except Exception as e:
                logger.exception(f"caught error while reading websocket messages")
                raise # re-raise error to terminate program. Supervisor will restart it


    async def on_connect(self):
        # this seems to not get called on first connect, only on reconnects
        #auto reconnects cause multiple connections sometimes, and sometimes we also stop getting messages
        # so force a reconnect
        self.connection_count += 1
        logger.debug(f"websocket connected, connection count is now {self.connection_count}")
        if self.connection_count > 1:
            #duplicate connections made somehow, conk out
            logger.error(f"too many websocket connections, {self.connection_count}, re-creating connection")
            await self.force_reconnect()

    async def force_reconnect(self):
        if self.connecting:
            logger.debug("already connecting, not forcing another reconnect")
            return

        try:
            self.connecting = True
            logger.info("forcing websocket reconnect")
            if self.server:
                await self.server.disconnect()
            self.server = None
            await asyncio.sleep(1)
            await self.connect(self.server_port)
        except Exception as e:
            logger.exception(f"caught exception while forcing reconnect: {e}")
        finally:
            self.connecting = False

    def on_disconnect(self):
        self.connection_count-= 1
        logger.debug(f"websocket disconnected, connection count is now {self.connection_count}")

    async def subscribe_doc(self, doctype, docname):
        self._doctype = doctype
        self._docname = docname
        await self.server.emit("doc_subscribe", (doctype, docname), namespace=f"/{self.namespace}")

    def observerFn(self,observer,scheduler):
        self.observer = observer

    def create_observable(self):
        logger.debug("creating websocket observable")
        return create(self.observerFn)
