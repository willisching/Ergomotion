import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity
from . import switch as switch_module

TIMER_CYCLE = ["10", "20", "30", None]


async def _stop_all_positions():
    for sw in switch_module._position_switches:
        if sw._attr_is_on:
            await sw.async_turn_off()


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]

    add_entities([
        XFlatButton(device, "scene"),
        XMassageButton(device, "back_massage"),
        XMassageButton(device, "foot_massage"),
        XTimerButton(device, "timer_target"),
    ])


class XFlatButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:stop"

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = "Stop"
        self._attr_unique_id = device.mac.replace(":", "") + "_flat_button"
        self.entity_id = (DOMAIN + "." + self._attr_unique_id).lower()

    async def async_press(self) -> None:
        await _stop_all_positions()
        self.device.set_attribute("scene", "flat")


class XMassageButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:sine-wave"

    async def async_press(self) -> None:
        await _stop_all_positions()
        self.device.set_attribute(self.attr, 1)


class XTimerButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:timer"
    _timer_index: int = -1

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = "Massage Timer"
        self._attr_unique_id = device.mac.replace(":", "") + "_timer_button"
        self.entity_id = (DOMAIN + "." + self._attr_unique_id).lower()

    async def async_press(self) -> None:
        self._timer_index = (self._timer_index + 1) % len(TIMER_CYCLE)
        self.device.set_attribute(self.attr, 1)
        self.device.current_state["timer_target"] = TIMER_CYCLE[self._timer_index]
        for handler in self.device.updates_state:
            handler()