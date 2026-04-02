from homeassistant.components.select import SelectEntity
from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    device = hass.data[DOMAIN][config_entry.entry_id]
    # Create a select entity for Scenes and one for the Massage Timer
    async_add_entities([
        ErgomotionSelect(device, "scene", "Bed Scene", ["flat", "snore", "memory1", "memory2", "memory3", "zerog"]),
    ])

class ErgomotionSelect(SelectEntity):
    def __init__(self, device, attr, name, options):
        self._device = device
        self._attr = attr
        self._attr_name = name
        self._attr_options = options

    @property
    def name(self): return self._attr_name

    @property
    def options(self): return self._attr_options

    @property
    def current_option(self):
        # We need to pull the current string from our device state
        return self._device.current_state.get(self._attr)

    async def async_select_option(self, option: str):
        # This calls the set_attribute we already built!
        self._device.set_attribute(self._attr, option)
        self.async_write_ha_state()