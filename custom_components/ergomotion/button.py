from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity

import asyncio

TIMER_OPTIONS = ["10", "20", "30"]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]

    add_entities([
        XFlatButton(device, "scene"),
        XMassageButton(device, "head_massage"),
        XMassageButton(device, "foot_massage"),
        XTimerButton(device, "timer_target"),
        XPositionButton(device, "head_up"),
        XPositionButton(device, "head_down"),
        XPositionButton(device, "foot_up"),
        XPositionButton(device, "foot_down"),
        XStopButton(device, "stop"),
    ])


class XFlatButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:bed-outline"
    _attr_name = "Stop"

    async def async_press(self) -> None:
        self.device.set_attribute(self.attr, "flat")


class XMassageButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:sine-wave"

    async def async_press(self) -> None:
        self.device.set_attribute(self.attr, 1)


class XTimerButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:timer"

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = device.name + " Massage Timer Button"
        self._attr_unique_id = device.mac.replace(":", "") + "_timer_button"
        self.entity_id = DOMAIN + "." + self._attr_unique_id
    
    async def async_press(self) -> None:
        self.device.set_attribute(self.attr, 1)


class XPositionButton(XEntity, ButtonEntity):
    ICONS = {
        "head_up":   "mdi:arrow-up-box",
        "head_down": "mdi:arrow-down-box",
        "foot_up":   "mdi:arrow-up-box",
        "foot_down": "mdi:arrow-down-box",
    }
    NAMES = {
        "head_up":   "Head Up",
        "head_down": "Head Down",
        "foot_up":   "Foot Up",
        "foot_down": "Foot Down",
    }
    MOVE_ATTR = {
        "head_up":   "head_move",
        "head_down": "head_move",
        "foot_up":   "foot_move",
        "foot_down": "foot_move",
    }

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = self.NAMES[attr]
        self._attr_icon = self.ICONS[attr]
        self._attr_unique_id = device.mac.replace(":", "") + "_" + attr
        self.entity_id = DOMAIN + "." + self._attr_unique_id
        self._moving = False

    async def async_press(self) -> None:
        if self._moving:
            return

        self._moving = True
        move_attr = self.MOVE_ATTR[self.attr]

        try:
            while True:
                self.device.set_attribute(self.attr, 1)
                await asyncio.sleep(0.3)

                # Stop if bed reports it's no longer moving (hit limit)
                if not self.device.current_state.get(move_attr):
                    break
        finally:
            self._moving = False

class XStopButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:stop"
    _attr_name = "Stop Movement"

    async def async_press(self) -> None:
        self.device.set_attribute(self.attr, None)