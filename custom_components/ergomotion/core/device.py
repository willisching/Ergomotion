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

    # Continuous Movement Commands (6 bytes)
    'head_up':          b'\x04\x02\x00\x00\x00\x10',
    'head_down':        b'\x04\x02\x00\x00\x00\x20',
    'foot_up':          b'\x04\x02\x00\x00\x00\x04',
    'foot_down':        b'\x04\x02\x00\x00\x00\x08',
    'lumbar_up':        b'\x04\x02\x00\x00\x40\x00',
    'lumbar_down':      b'\x04\x02\x00\x00\x80\x00',
    'neck_up':          b'\x04\x02\x00\x00\x00\x01',
    'neck_down':        b'\x04\x02\x00\x00\x00\x02',
    
    # Preset Commands (6 bytes) - Mapped to SCENE_OPTIONS
    'flat':             b'\x04\x02\x08\x00\x00\x00',
    'zerog':            b'\x04\x02\x00\x00\x10\x00',
    'snore':            b'\x04\x02\x00\x00\x80\x00',
    'memory1':          b'\x04\x02\x00\x01\x00\x00',
    'memory2':          b'\x04\x02\x00\x00\x20\x00',
    'memory3':          b'\x04\x02\x00\x00\x40\x00',

    # Toggle/Cycle Commands
    'head_massage':     b'\x04\x02\x00\x00\x08\x00',
    'foot_massage':     b'\x04\x02\x00\x00\x04\x00',
    'led_toggle':       b'\x04\x02\x00\x02\x00\x00',
    'timer_cycle':      b'\x04\x02\x00\x00\x02\x00'
}


class Attribute(TypedDict, total=False):
    is_on: bool  # binary_sensor

    position: int  # cover
    move: bool  # cover

    percentage: int

    current: str  # select
    options: list[str]  # select

    extra: dict  # entity


class Device:
    def __init__(self, name: str, device: BLEDevice | None):
        self.name = name

        self.client = Client(device, self.on_data) if device else None

        self.connected = False

        self.current_data = None
        self.current_state = {}

        self.target_delay = 0
        self.target_state = {}

        self.updates_connect: list = []
        self.updates_state: list = []

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
        _LOGGER.debug("on_data")
        
        # data packet example from what i can tell
        #                                                data1                                       data2
        #                                  |~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|       |~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|
        # position:         0  1  2        3   4        5        6        7        8  9        10 11       12       13 14 15
        # bytes:			A5 0B 0D       00 00       00       00       00        00 00       00 00       00       00 00 00
        #                   |~~~~~~|       |~~~|       ||       ||       ||        |~~~|       |~~~|       ||       |~~~~~~| 
        # field:	   		constant       massage     unused   head     foot      head        foot        light    unused
        #                                  time                 massage  massage   position    position
        #                                  left (seconds)
        # decimal value:	               1800                 1/3/6    1/3/6    ?*           ?*           0/1
        # 
        # Notes:
        # - * not entirely sure what the max value is as testing kept getting slightly different results
        # - the only times that data seems to be sent is when returning to flat, timer, or massage buttons are pressed

        if isinstance(data, bool):
            _LOGGER.debug("isinstance")
            # connected true/false update
            self.connected = data

            for handler in self.updates_connect:
                handler()
            return

        if self.current_data != data:
            # we're assuming a length of 20 but idk; could be 16?
            if data[0] == 0xED and len(data) == 16:
                _LOGGER.debug("length: 16")
                self.parse_data(data, data[3:], data[8:])
            elif data[0] == 0xF0 and len(data) == 19:
                _LOGGER.debug("length: 19")
                self.parse_data(data, data[3:], data[8:])
            elif data[0] == 0xF1 and len(data) == 20:
                _LOGGER.debug("length: 20")
                self.parse_data(data, data[3:], data[8:])


        if self.target_state:
            self.send_command()

    def parse_data(self, data: bytes, data1: bytes, data2: bytes):
        _LOGGER.debug("parse_data")
        self.current_data = data

        head_position = int.from_bytes(data2[0:2], "little")
        foot_position = int.from_bytes(data2[2:4], "little")

        # unsure about these
        remain = int.from_bytes(data1[0:2], "little")
        move = data2[4] & 0xF if data[0] != 0xF1 else 0xF
        timer = data2[5]

        self.current_state = {
            "head_position": head_position if head_position != 0xFFFF else 0,
            "foot_position": foot_position if foot_position != 0xFFFF else 0,

            "head_move": move != 0xF and move & 1 > 0,
            "foot_move": move != 0xF and move & 2 > 0,

            # data does not have info on these from what i can tell
            #"lumbar_position": 0, 
            #"back_position": 0, 
            #"lumbar_move": False,
            #"back_move": False,
            
            # only 1/3/6 for intensity
            "head_massage": int(data1[4] / 6 * 100),
            "foot_massage": int(data1[5] / 6 * 100),

            "timer_target": TIMER_OPTIONS[timer - 1] if timer != 0xFF else None,
            # remain should be in seconds, so not certain why/ 100
            #"timer_remain": round(remain / 100),
            "timer_remain": remain,
            "led": data2[4] & 0x40 > 0,
        }

        self.current_state["scene"] = (
            self.current_state["head_position"] > MIN_STEP
            or self.current_state["foot_position"] > MIN_STEP
            or self.current_state["head_massage"] > 0
            or self.current_state["foot_massage"] > 0
        )

        for handler in self.updates_state:
            handler()

    def attribute(self, attr: str) -> Attribute:
        _LOGGER.debug("attribute")
        if attr == "connection":
            return Attribute(
                is_on=self.connected, extra={"mac": self.client.device.address}
            )

        if attr in ("head_position", "foot_position"):
            move_attr = attr.replace("position", "move")
            return Attribute(
                position=self.current_state.get(attr),
                move=self.current_state.get(move_attr),
            )

        if attr in ("head_massage", "foot_massage"):
            if percent := self.current_state.get(attr):
                return Attribute(
                    percentage=percent,
                    current=self.current_state.get("timer_target"),
                    options=TIMER_OPTIONS,
                )
            else:
                return Attribute(percentage=percent, options=TIMER_OPTIONS)

        if attr == "scene":
            remain = self.current_state.get("timer_remain")
            return Attribute(
                is_on=self.current_state.get(attr),
                options=SCENE_OPTIONS,
                extra={"timer_remain": remain} if remain else None,
            )

        if attr == "led":
            return Attribute(is_on=self.current_state.get(attr))

    def set_attribute(self, name: str, value: int | str | bool | None):
        _LOGGER.debug(f"set_attribute: {name}")
        self.target_state[name] = value
        self.client.ping()
        # testing to see if can just send
        if self.target_state:
            self.send_command()

    def send_command(self):
        _LOGGER.debug("send_command")
        # idk if there's a "stop"; from what i've seen it's just another command interupts to stop
        if "stop" in self.target_state:
            self.target_state.clear()
            self.client.send(COMMANDS_NUS_6BYTE['flat'])
            return

        command_to_send = None
        
        for attr, target in list(self.target_state.items()):
            current = self.current_state.get(attr)
            
            is_continuous = attr.endswith("_position")
            
            if is_continuous:
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
                # figure out what to do with lumbar and back if nothing comes back
                #elif attr == "lumbar_position":
                #    key = 'lumbar_up' if current < target else 'lumbar_down'
                #elif attr == "back_position":
                #    key = 'back_up' if current < target else 'back_down'

                if key and (command_to_send := COMMANDS_NUS_6BYTE.get(key)):
                    break # Send only one continuous command per cycle

            
            # Massage (Single-push cycle/toggle)
            elif attr in ("head_massage", "foot_massage"):
                # If target is 0, we assume the user wants the massage OFF, so we clear the target.
                if target == 0:
                    self.target_state.pop(attr)
                    continue
                
                # If target is > 0, we push the button once to start/cycle.
                if command_to_send := COMMANDS_NUS_6BYTE.get(attr):
                    # Do not pop target. Keep it until user manually sets to 0.
                    break 

            # Scene Presets (light.py turn_on/turn_off sends scene names)
            elif attr == "scene":
                if command_to_send := COMMANDS_NUS_6BYTE.get(target):
                    self.target_state.pop(attr) 
                    break
            
            # LED (light.py sends True/False)
            elif attr == "led":
                current_is_on = self.current_state.get('led')
                if current_is_on != target:
                    if command_to_send := COMMANDS_NUS_6BYTE.get('led_toggle'):
                        self.target_state.pop(attr)
                        break
            
            # Timer (fan.py set_preset_mode sends '10', '20', '30', but command is a cycle)
            elif attr == "timer_target":
                if command_to_send := COMMANDS_NUS_6BYTE.get('timer_cycle'):
                    self.target_state.pop(attr)
                    break

        if command_to_send:
            self.client.send(command_to_send)
        
        elif self.current_state.get("head_move") or self.current_state.get("foot_move"):
            self.client.send(COMMANDS_NUS_6BYTE['flat'])

