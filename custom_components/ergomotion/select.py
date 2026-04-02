from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity

PRESETS = ["flat", "snore", "memory1", "memory2", "memory3", "zerog"]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]
    add_entities([XPreset(device, "scene")])


class XPreset(XEntity, SelectEntity):
    _attr_icon = "mdi:bed"
    _attr_options = PRESETS

    def internal_update(self):
        attribute = self.device.attribute(self.attr)

        # Try to get the current preset from the device state
        current = attribute.get("current")
        if current in PRESETS:
            self._attr_current_option = current
        else:
            self._attr_current_option = None

        if self.hass:
            self._async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self.device.set_attribute(self.attr, option)
        self._attr_current_option = option
        self._async_write_ha_state()