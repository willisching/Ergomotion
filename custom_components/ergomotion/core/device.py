import time
import logging
from typing import TypedDict, Callable

from bleak import BLEDevice, BleakGATTCharacteristic

from .client import Client

_LOGGER = logging.getLogger(__name__)
MIN_STEP = 100
SCENE_OPTIONS = ["flat", "snore", "memory1", "memory2", "memory3", "zerog"] 
TIMER_OPTIONS = ["10", "20", "30"]


COMMANDS_NUS_6BYTE = {
    'head_up':             b'\x04\x02\x00\x00\x00\x10',
    'head_down':           b'\x04\x02\x00\x00\x00\x20',
    'foot_up':             b'\x04\x02\x00\x00\x00\x04',
    'foot_down':           b'\x04\x02\x00\x00\x00\x08',
    'lumbar_up':           b'\x04\x02\x00\x00\x40\x00',
    'lumbar_down':         b'\x04\x02\x00\x00\x80\x00',
    'neck_up':             b'\x04\x02\x00\x00\x00\x01',
    'neck_down':           b'\x04\x02\x00\x00\x00\x02',
    'flat':                b'\x04\x02\x08\x00\x00\x00',
    'zerog':               b'\x04\x02\x00\x00\x10\x00',
    'snore':               b'\x04\x02\x00\x00\x80\x00',
    'memory1':             b'\x04\x02\x00\x01\x00\x00',
    'memory2':             b'\x04\x02\x00\x00\x20\x00',
    'memory3':             b'\x04\x02\x00\x00\x40\x00',
    'stop':                b'\x04\x02\x08\x00\x00\x00', 
    'head_massage':        b'\x04\x02\x00\x00\x08\x00',
    'foot_massage':        b'\x04\x02\x00\x00\x04\x00',
    'led_toggle':          b'\x04\x02\x00\x02\x00\x00',
    'timer_cycle':         b'\x04\x02\x00\x00\x02\x00'
}


class Attribute(TypedDict, total=False):
    is_on: bool 
    position: int 
    move: bool 
    percentage: int
    current: str 
    options: list[str] 
    extra: dict 


class Device:
    def __init__(self, name: str, device: BLEDevice | None):
        self.name = name
        self.client = Client(device, self.on_data) if device else None
        self.connected = False
        self.current_data = None
        
        # FIX: Initialize current_state with 0 for all position and numeric attributes
        self.current_state = {
            "head_position": 0,
            "foot_position": 0,
            "head_move": False,
            "foot_move": False,
            "head_massage": 0,
            "foot_massage": 0,
            "timer_target": None,
            "timer_remain": 0,
            "led": False,
            "scene": False,
        }
        
        self.target_delay = 0
        self.target_state = {}
        self.updates_connect: list = []
        self.updates_state: list = []
        self.request_counter = 0 
        
    @property
    def mac(self) -> str:
        return self.client.device.address

    def register_update(self, attr: str, handler: Callable):
        _LOGGER.debug("register_update")
        if attr == "connection":
            self.updates_connect.append(handler)
        else:
            self.updates_state.append(handler)

    def on_data(self, char: BleakGATTCharacteristic | None, data: bytes | bool):
        _LOGGER.debug(f"on_data: {data}")

        if isinstance(data, bool):
            _LOGGER.debug("isinstance")
            self.connected = data
            for handler in self.updates_connect:
                handler()
            return

        if self.current_data != data:
            if data and len(data) >= 16:
                # Assuming parsing works for the different headers/lengths
                if data[0] == 0xED and len(data) == 16:
                    self.parse_data(data, data[3:], data[8:])
                elif data[0] == 0xF0 and len(data) == 19:
                    self.parse_data(data, data[3:], data[8:])
                elif data[0] == 0xF1 and len(data) == 20:
                    self.parse_data(data, data[3:], data[8:])
                elif data[0] == 0xA5 and len(data) >= 16:
                    self.parse_data(data, data[3:8], data[8:]) 

        
        # --- COMMAND-AND-REQUEST LOOP LOGIC ---
        if self.target_state:
            # If we are moving, continue to send commands until target is met
            self.send_command() 
        else:
            # If we are idle, send a periodic status request to keep the state fresh
            self.request_counter += 1
            if self.request_counter % 5 == 0:
                 if self.client and self.client.connected:
                    self.client.request_status()
                    self.request_counter = 0


    def parse_data(self, data: bytes, data1: bytes, data2: bytes):
        _LOGGER.debug("parse_data")
        self.current_data = data

        # Parsing logic: Uses 0xFFFF check for uninitialized values, but 
        # the __init__ pre-fill handles the first-run safety.
        head_position = int.from_bytes(data2[0:2], "little")
        foot_position = int.from_bytes(data2[2:4], "little")
        remain = int.from_bytes(data1[0:2], "little")
        move = data2[4] & 0xF if len(data2) > 4 and data[0] != 0xF1 else 0xF
        timer = data2[5] if len(data2) > 5 else 0xFF

        self.current_state.update({
            "head_position": head_position if head_position != 0xFFFF else 0,
            "foot_position": foot_position if foot_position != 0xFFFF else 0,
            "head_move": move != 0xF and move & 1 > 0,
            "foot_move": move != 0xF and move & 2 > 0,
            "head_massage": int(data1[4] / 6 * 100) if len(data1) > 4 else 0,
            "foot_massage": int(data1[5] / 6 * 100) if len(data1) > 5 else 0,
            "timer_target": TIMER_OPTIONS[timer - 1] if timer != 0xFF and 0 < timer <= len(TIMER_OPTIONS) else None,
            "timer_remain": remain,
            "led": data2[4] & 0x40 > 0 if len(data2) > 4 else False,
        })

        self.current_state["scene"] = (
            self.current_state["head_position"] > MIN_STEP
            or self.current_state["foot_position"] > MIN_STEP
            or self.current_state["head_massage"] > 0
            or self.current_state["foot_massage"] > 0
        )

        for handler in self.updates_state:
            handler()

    # ... (attribute method unchanged)

    def set_attribute(self, name: str, value: int | str | bool | None):
        _LOGGER.debug(f"set_attribute name: {name}")
        _LOGGER.debug(f"set_attribute value: {value}")
        self.target_state[name] = value
        
        # Send the first command immediately to start the movement/action
        if self.client and self.client.connected:
            self.send_command()
        
        self.client.ping()

    def attribute(self, name: str) -> Attribute:
        """Returns the current state dictionary for a specific attribute name."""
        
        # This function needs to return a dictionary object that includes:
        # 'is_on' (for sensors/lights), 'position' (for covers), etc.

        if name == "head_position":
            return Attribute(
                position=self.current_state["head_position"],
                move=self.current_state["head_move"],
            )
        elif name == "foot_position":
            return Attribute(
                position=self.current_state["foot_position"],
                move=self.current_state["foot_move"],
            )
        elif name == "connection":
            return Attribute(
                is_on=self.connected,
            )
        elif name == "led":
            return Attribute(
                is_on=self.current_state["led"],
            )
        # Add other attributes here (massage, timer, etc.) as needed by your integration files.
        # This structure is common for Home Assistant integrations.
        
        return Attribute()

    def send_command(self):
        _LOGGER.debug("send_command")
        
        if "stop" in self.target_state:
            self.target_state.clear()
            self.client.send(COMMANDS_NUS_6BYTE['stop']) 
            return

        command_to_send = None
        
        for attr, target in list(self.target_state.items()):
            current = self.current_state.get(attr)
            is_continuous = attr.endswith("_position")
            
            if is_continuous:
                # This line now works because current is guaranteed to be an int (0 or the last known pos)
                is_reached = abs(current - target) < MIN_STEP
                
                if is_reached:
                    self.client.send(COMMANDS_NUS_6BYTE['stop'])
                    self.target_state.pop(attr)
                    continue

                key = None
                if attr == "head_position":
                    key = 'head_up' if current < target else 'head_down'
                elif attr == "foot_position":
                    key = 'foot_up' if current < target else 'foot_down'
                
                if key and (command_to_send := COMMANDS_NUS_6BYTE.get(key)):
                    break 

            elif attr in ("head_massage", "foot_massage"):
                if target == 0:
                    self.target_state.pop(attr)
                    continue
                if command_to_send := COMMANDS_NUS_6BYTE.get(attr):
                    self.target_state.pop(attr) 
                    break 

            elif attr == "scene":
                if command_to_send := COMMANDS_NUS_6BYTE.get(target):
                    self.target_state.pop(attr) 
                    break
            
            elif attr == "led":
                current_is_on = self.current_state.get('led')
                if current_is_on != target:
                    if command_to_send := COMMANDS_NUS_6BYTE.get('led_toggle'):
                        self.target_state.pop(attr)
                        break
            
            elif attr == "timer_target":
                if command_to_send := COMMANDS_NUS_6BYTE.get('timer_cycle'):
                    self.target_state.pop(attr)
                    break

        if command_to_send:
            self.client.send(command_to_send)
            # CRITICAL: Send status request immediately after motor command
            self.client.request_status()
        
        elif not self.target_state and (self.current_state.get("head_move") or self.current_state.get("foot_move")):
            self.client.send(COMMANDS_NUS_6BYTE['stop'])