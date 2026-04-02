from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]
    add_entities([
        XTimerSensor(device, "timer_target"),
        #XTimerRemainSensor(device, "timer_remain"),
    ])


class XTimerSensor(XEntity, SensorEntity):
    _attr_icon = "mdi:timer"
    _attr_name = "Massage Timer"

    def internal_update(self):
        self._attr_native_value = self.device.current_state.get("timer_target") or "off"
        if self.hass:
            self._async_write_ha_state()


""" class XTimerRemainSensor(XEntity, SensorEntity):
    _attr_icon = "mdi:timer-sand"
    _attr_name = "Massage Timer Remaining"
    _attr_native_unit_of_measurement = "s"

    def internal_update(self):
        self._attr_native_value = self.device.current_state.get("timer_remain") or 0
        if self.hass:
            self._async_write_ha_state() """