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
        XHeadUp(device, "head_position"),
        XHeadDown(device, "head_position"),
        XFootUp(device, "foot_position"),
        XFootDown(device, "foot_position"),
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
    _attr_name = "Massage Timer"

    async def async_press(self) -> None:
        self.device.set_attribute(self.attr, 1)

class XHeadUp(XEntity, ButtonEntity):
    _attr_icon = "mdi:arrow-up-box"
    _attr_name = "Head Up"

    async def async_press(self) -> None:
        self.device.set_attribute("head_position", 1)


class XHeadDown(XEntity, ButtonEntity):
    _attr_icon = "mdi:arrow-down-box"
    _attr_name = "Head Down"

    async def async_press(self) -> None:
        self.device.set_attribute("head_position", -1)


class XFootUp(XEntity, ButtonEntity):
    _attr_icon = "mdi:arrow-up-box"
    _attr_name = "Foot Up"

    async def async_press(self) -> None:
        self.device.set_attribute("foot_position", 1)


class XFootDown(XEntity, ButtonEntity):
    _attr_icon = "mdi:arrow-down-box"
    _attr_name = "Foot Down"

    async def async_press(self) -> None:
        self.device.set_attribute("foot_position", -1)