import asyncio
import logging
import time
from typing import Callable, Optional

from bleak import BleakClient, BLEDevice, BleakError, BleakGATTCharacteristic
from bleak_retry_connector import establish_connection

_LOGGER = logging.getLogger(__name__)

ACTIVE_TIME = 120 # seconds

# --- CONSTANTS FOR COMMUNICATION ---
# The UUID for the WRITE characteristic (where you send commands)
COMMAND_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
# The UUID for the NOTIFY/READ status characteristic
STATUS_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

# The safest command to send to ask for a status update without causing movement.
STATUS_REQUEST_COMMAND = b'\x04\x02\x00\x00\x00\x00' 


class Client:
    def __init__(self, device: BLEDevice, callback: Callable):
        self.device = device
        self.callback = callback

        self.client: Optional[BleakClient] = None

        self.ping_task: Optional[asyncio.Task] = None
        self.ping_time = 0

        self.send_task: Optional[asyncio.Task] = None
        self.send_data: Optional[bytes] = None
        
        # self.poll_task is removed as polling is now manual via request_status()

        self.ping()

    def ping(self):
        self.ping_time = time.time() + ACTIVE_TIME

        if not self.ping_task:
            self.ping_task = asyncio.create_task(self._ping_loop())

    async def _ping_loop(self):
        while self.ping_time > time.time():
            try:
                _LOGGER.debug("connecting...")

                self.client = await establish_connection(
                    BleakClient, self.device, self.device.address
                )

                self.callback(char=None, data=True)

                # Attempt to start notify (Still necessary to receive spontaneous movement updates)
                await self.client.start_notify(
                    STATUS_CHAR_UUID, self.callback
                )
                
                # Manual request for status update right after connecting
                await self.client.write_gatt_char(
                    COMMAND_CHAR_UUID, STATUS_REQUEST_COMMAND, False
                )
                
                _LOGGER.debug("connected and status requested")

                while (delay := self.ping_time - time.time()) > 0:
                    await asyncio.sleep(delay)

                _LOGGER.debug("disconnecting...")
                
                # Stop notifications before disconnecting
                await self.client.stop_notify(STATUS_CHAR_UUID)
                
                await self.client.disconnect()
            except TimeoutError:
                pass
            except BleakError as e:
                _LOGGER.debug("ping error", exc_info=e)
            except Exception as e:
                _LOGGER.warning("ping error", exc_info=e)
            finally:
                # No poll_task to cancel
                self.client = None
                self.callback(None, False)
                await asyncio.sleep(1)

        self.ping_task = None

    def request_status(self):
        """Manually sends the zero command to request a fresh status report."""
        if self.client and self.client.is_connected and not self.send_task:
            _LOGGER.debug(f"Requesting status with command: {STATUS_REQUEST_COMMAND.hex()}")
            self.send(STATUS_REQUEST_COMMAND)


    def send(self, data: bytes):
        self.send_data = data
        _LOGGER.debug(f"send command: {self.send_task}")
        if self.client and self.client.is_connected and not self.send_task:
            _LOGGER.debug("in send asyncio")
            self.send_task = asyncio.create_task(self._send_coro())

    async def _send_coro(self):
        try:
            _LOGGER.debug(f"send coro: {self.send_data.hex()}")
            await self.client.write_gatt_char(
                COMMAND_CHAR_UUID, self.send_data, False
            )
        except Exception as e:
            _LOGGER.warning("send error", exc_info=e)
        self.send_task = None