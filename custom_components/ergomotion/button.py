import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity

TIMER_CYCLE = ["10", "20", "30", None]
POSITION_SEND_INTERVAL = 0.2  # seconds between repeated commands
POSITION_MAX_DURATION = 30    # safety cutoff in seconds


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

    # Track timer state locally since bed sends no feedback
    _timer_index: int = -1  # -1 = off, 0/1/2 = 10/20/30

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = device.name + " Massage Timer Button"
        self._attr_unique_id = device.mac.replace(":", "") + "_timer_button"
        self.entity_id = DOMAIN + "." + self._attr_unique_id

    async def async_press(self) -> None:
        self._timer_index = (self._timer_index + 1) % len(TIMER_CYCLE)
        self.device.set_attribute(self.attr, 1)

        # Push the local timer value into current_state so sensors update
        self.device.current_state["timer_target"] = TIMER_CYCLE[self._timer_index]
        for handler in self.device.updates_state:
            handler()


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

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        self._attr_name = self.NAMES[attr]
        self._attr_icon = self.ICONS[attr]
        self._attr_unique_id = device.mac.replace(":", "") + "_" + attr
        self.entity_id = DOMAIN + "." + self._attr_unique_id
        # Store moving flag on the device itself, keyed by axis
        # so head_up and head_down share the same flag
        self._axis = "head" if "head" in attr else "foot"

    async def async_press(self) -> None:
        axis_flag = f"_moving_{self._axis}"

        if getattr(self.device, axis_flag, False):
            setattr(self.device, axis_flag, False)
            return

        setattr(self.device, axis_flag, True)
        deadline = asyncio.get_event_loop().time() + POSITION_MAX_DURATION

        try:
            while getattr(self.device, axis_flag, False) and asyncio.get_event_loop().time() < deadline:
                self.device.client.ping()  # ← keep connection alive
                self.device.set_attribute(self.attr, 1)
                await asyncio.sleep(POSITION_SEND_INTERVAL)
        finally:
            setattr(self.device, axis_flag, False)


class XStopButton(XEntity, ButtonEntity):
    _attr_icon = "mdi:stop"
    _attr_name = "Stop Movement"

    async def async_press(self) -> None:
        # Stop any running position loops
        self.device.set_attribute("stop", None)