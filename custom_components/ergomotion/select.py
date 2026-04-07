from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity
from . import switch as switch_module

PRESETS = ["Flat", "Anti Snore", "Memory 1", "Memory 2", "Memory 3", "Zero G"]


async def _stop_all_positions():
    for sw in switch_module._position_switches:
        if sw._attr_is_on:
            await sw.async_turn_off()


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]
    add_entities([XPreset(device, "scene")])


class XPreset(XEntity, SelectEntity):
    _attr_icon = "mdi:bed"
    _attr_options = PRESETS

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = "Preset"
        self._attr_unique_id = device.mac.replace(":", "") + "_preset"
        self.entity_id = (DOMAIN + "." + self._attr_unique_id).lower()

    def internal_update(self):
        current = self.device.current_state.get("scene")
        self._attr_current_option = current if current in PRESETS else None
        if self.hass:
            self._async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        await _stop_all_positions()
        self.device.set_attribute(self.attr, option)
        self._attr_current_option = option
        self._async_write_ha_state()