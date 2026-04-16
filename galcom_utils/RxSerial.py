import json
import asyncio
import re
import time
import logging
from rx import create
from serial import Serial
from serial.serialutil import SerialException

logger = logging.getLogger("main")

class ParseError(Exception):
    pass
class SerialCrash(Exception):
    pass 

class RxSerial:


    def __init__(self,resetFn,serial_ports=["/dev/ttyUSB0","/dev/ttyUSB1"]):
        self.serial_ports = serial_ports
        self.resetFn = resetFn
        self.loop = asyncio.get_event_loop()
        self.failure_count=0

    async def connect(self):
        try:
            logger.debug(f"connecting to serial port, will try {self.serial_ports}")
            for port in self.serial_ports:
                try:
                    self.ser = Serial(port, baudrate=115200)
                    self.ser.inWaiting()
                    logger.debug(f"connected to serial port {port}")
                    self.resetFn(self)
                    return
                except OSError:
                    logger.warning(f"failed to connect to port {port}")

            logger.warning("failed to connect to any serial port, waiting to try again")
            await asyncio.sleep(10)
            await self.connect()
        except Exception as e:
            logger.exception(f"caught error in serial init {e}")

    def read_observer(self,observer,scheduler):
        logger.debug("starting serial read observer")

        async def get_messages():
            while True:
                try:
                    if self.ser.inWaiting():
                        packet = self.ser.readline()
                        try:
                            data = packet.decode('utf-8').rstrip('\n')
                            serial_data = SerialData(data)
                            logger.info(f"S<-- {data}")
                            observer.on_next(serial_data)
                        except UnicodeDecodeError:
                            logger.exception(f"failed to decode packet {packet}")
                        except ParseError:
                            pass
                            #parse errors are generally debug output coming from player, so just ignore it
                        except SerialCrash:
                            logger.info("running onCrashFn to recover")
                            time.sleep(2) #wait for device to reboot
                            await self.connect()
                    else:
                        await asyncio.sleep(0.01)
                except Exception as e:
                    logger.exception(f"caught error while reading serial messages")
                    try:
                        self.ser.close()
                    except:
                        pass
                    await self.connect()

        self.loop.create_task(get_messages())

    def create_read_observable(self):
        return create(self.read_observer)

    def send_message(self,message):
        logger.info(f"-->S {message}")
        self.ser.write((message+"\n").encode('ascii'))


class SerialData:
    mac: str
    type: int
    command: int
    data: str = ''
    crashRE = re.compile(r".*CUT HERE FOR EXCEPTION DECODER.*")

    def __init__(self,in_data=None):
        if in_data:
            self.parse(in_data)

    def __str__(self):
        return(f"SerialData - Mac: {self.mac}  type: {self.type}  command: {self.command}  Data: {self.data}")

    def set(self,mac,type,command,data=""):
        self.mac=mac
        self.type=type
        self.command=command
        self.data=data
        return self #allow chaining

    def as_message(self):
        try:
            data = json.loads(self.data) if self.data and self.data != "" else {}
        except json.JSONDecodeError:
            data = {"error":f"failed to parse data: {self.data}"}

        return {
            "mac":self.mac,
            "type":self.type,
            "command":self.command,
            "data":data
        }

    def parse(self, in_data: str) -> bool:
        is_mac = re.search(r"^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})", in_data)
        if is_mac:
            self.mac = is_mac[0]
            self.type = int(in_data[18:20], 16)
            try:
                self.command = int(in_data[21:23], 16)
            except ValueError:
                self.command = 0
            find_txt = re.search(r'"(.*)"', in_data)
            if find_txt:
                self.data = find_txt[0].strip('"')
        elif self.crashRE.match(in_data):
            logger.warning("Serial device seems to have crashed")
            raise SerialCrash
        else:
            logger.debug(f"    debug: {in_data}")
            raise ParseError
