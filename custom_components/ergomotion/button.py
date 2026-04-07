import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import switch as switch_module
from .core import DOMAIN
from .core.entity import XEntity

TIMER_CYCLE = ["10", "20", "30", None]

PRESETS = ["flat", "snore", "memory1", "memory2", "memory3", "zerog"]

PRESET_NAMES = {
    "flat":    "Flat",
    "snore":   "Anti Snore",
    "memory1": "Memory 1",
    "memory2": "Memory 2",
    "memory3": "Memory 3",
    "zerog":   "Zero G",
}

async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]

    add_entities([
        XPresetButton(device, preset) for preset in PRESETS
    ] + [
        XMassageButton(device, "head_massage", "Massage Back"),
        XMassageButton(device, "foot_massage", "Massage Feet"),
        XTimerButton(device, "timer_target"),
    ])


class XPresetButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:bed"

    def __init__(self, device, preset: str):
        super().__init__(device, "scene")
        self._attr_name = device.name + " " + PRESET_NAMES[preset]
        self._attr_unique_id = device.mac.replace(":", "") + "_preset_" + preset
        self.entity_id = (DOMAIN + "." + self._attr_unique_id).lower()
        self._preset = preset

    async def async_press(self) -> None:
        await _stop_all_positions()
        self.device.set_attribute("scene", self._preset)

async def _stop_all_positions():
    for sw in switch_module._position_switches:
        if sw._attr_is_on:
            await sw.async_turn_off()

class XMassageButton(XEntity, ButtonEntity):

    def __init__(self, device, attr: str, name: str):
        super().__init__(device, attr)
        self._attr_name = device.name + " " + name
        self._attr_unique_id = device.mac.replace(":", "") + "_" + attr + "_button"
        self.entity_id = (DOMAIN + "." + self._attr_unique_id).lower()
        self._attr_icon = "mdi:sine-wave"

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