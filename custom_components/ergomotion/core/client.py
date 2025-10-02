import asyncio
import logging
import time
from typing import Callable, Optional

from bleak import BleakClient, BLEDevice, BleakError, BleakGATTCharacteristic
from bleak_retry_connector import establish_connection

_LOGGER = logging.getLogger(__name__)

ACTIVE_TIME = 120  # seconds

# --- CONSTANTS FOR COMMUNICATION ---
# The UUID for the WRITE characteristic (where you send commands)
COMMAND_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
# The UUID for the NOTIFY/READ status characteristic
STATUS_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
# How often to check the status if notifications are not working (seconds)
POLL_INTERVAL = 1

# --- TEST WAKE-UP COMMAND ---
# This is a test, based on your 'flat' command from device.py
WAKEUP_COMMAND_TEST = b'\x04\x02\x08\x00\x00\x00'

class Client:
    def __init__(self, device: BLEDevice, callback: Callable):
        self.device = device
        self.callback = callback

        self.client: Optional[BleakClient] = None

        self.ping_task: Optional[asyncio.Task] = None
        self.ping_time = 0

        self.send_task: Optional[asyncio.Task] = None
        self.send_data: Optional[bytes] = None
        
        # New polling task to manually read status
        self.poll_task: Optional[asyncio.Task] = None # <-- NEW

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

                # 1. Attempt to start notify
                await self.client.start_notify(
                    STATUS_CHAR_UUID, self.callback
                )
                
                # 2. SEND THE WAKE-UP COMMAND TEST
                _LOGGER.debug(f"Sending wake-up test command: {WAKEUP_COMMAND_TEST.hex()}")
                await self.client.write_gatt_char(
                    COMMAND_CHAR_UUID, WAKEUP_COMMAND_TEST, False
                )
                
                # 3. START POLLING
                self.poll_task = asyncio.create_task(self._poll_status())
                
                _LOGGER.debug("connected")

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
                # --- CANCEL POLLING TASK ---
                if self.poll_task: # <-- NEW
                    self.poll_task.cancel()
                    self.poll_task = None
                
                self.client = None
                self.callback(None, False)
                await asyncio.sleep(1)

        self.ping_task = None

    # --- NEW POLLING COROUTINE ---
    async def _poll_status(self):
        """Repeatedly reads the status characteristic to get state data."""
        while self.client and self.client.is_connected:
            try:
                # 1. READ the characteristic value
                data = await self.client.read_gatt_char(STATUS_CHAR_UUID)
                
                # 2. Pass the data to the device callback for parsing (self.callback is Device.on_data)
                self.callback(char=None, data=data)
                
            except asyncio.CancelledError:
                # Exit cleanly when the task is cancelled (during disconnect)
                raise
            except BleakError as e:
                _LOGGER.debug(f"Polling read error: {e}")
            except Exception as e:
                _LOGGER.warning(f"Unexpected polling error: {e}")
            
            # 3. Wait for the interval before polling again
            await asyncio.sleep(POLL_INTERVAL)

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
                COMMAND_CHAR_UUID, self.send_data, False # Use new constant
            )
        except Exception as e:
            _LOGGER.warning("send error", exc_info=e)

        self.send_task = None