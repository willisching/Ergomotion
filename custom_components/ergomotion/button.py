from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity

TIMER_CYCLE = ["10", "20", "30", None]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]

    add_entities([
        XFlatButton(device, "scene"),
        XMassageButton(device, "head_massage"),
        XMassageButton(device, "foot_massage"),
        XTimerButton(device, "timer_target"),
    ])


class XFlatButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:bed-outline"
    _attr_name = "Flat"

    async def async_press(self) -> None:
        self.device.set_attribute(self.attr, "flat")


class XMassageButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:sine-wave"

    async def async_press(self) -> None:
        self.device.set_attribute(self.attr, 1)


class XTimerButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:timer"
    _attr_name = "Massage Timer"

    async def async_press(self) -> None:
        head = self.device.attribute("head_massage").get("percentage") or 0
        foot = self.device.attribute("foot_massage").get("percentage") or 0

        if head == 0 and foot == 0:
            self.device.set_attribute("head_massage", 1)
            self.device.set_attribute("foot_massage", 1)
            return

        current = self.device.attribute(self.attr).get("current")
        try:
            idx = TIMER_CYCLE.index(current)
        except ValueError:
            idx = -1

        next_timer = TIMER_CYCLE[(idx + 1) % len(TIMER_CYCLE)]
        self.device.set_attribute(self.attr, next_timer)