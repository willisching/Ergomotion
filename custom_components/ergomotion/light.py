from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]
    add_entities([XLed(device, "led")])

class XLed(XEntity, LightEntity):
    _attr_supported_color_modes = ColorMode.ONOFF

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = device.name + " Underbed Light"
        self._attr_unique_id = device.mac.replace(":", "") + "_led"
        self.entity_id = (DOMAIN + "." + self._attr_unique_id).lower()

    def internal_update(self):
        attribute = self.device.attribute(self.attr)

        self._attr_is_on = attribute.get("is_on")

        if self.hass:
            self._async_write_ha_state()

    async def async_turn_on(self, effect: str = None, **kwargs) -> None:
        self.device.set_attribute(self.attr, True)

    async def async_turn_off(self, **kwargs) -> None:
        self.device.set_attribute(self.attr, False)
