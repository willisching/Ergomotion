import asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import DOMAIN
from .core.entity import XEntity

POSITION_SEND_INTERVAL = 0.3
POSITION_MAX_DURATION = 30
RECONNECT_WAIT_INTERVAL = 0.5

POSITION_ATTRS = {
    "back_up":    ("Raise Back",    "mdi:arrow-up-box"),
    "back_down":  ("Lower Back",  "mdi:arrow-down-box"),
    "feet_up":    ("Raise Feet",    "mdi:arrow-up-box"),
    "feet_down":  ("Lower Feet",  "mdi:arrow-down-box"),
    "lumbar_up":  ("Raise Lumbar",  "mdi:arrow-up-box"),
    "lumbar_down":("Lower Lumbar","mdi:arrow-down-box"),
    "head_up":    ("Raise Head",    "mdi:arrow-up-box"),
    "head_down":  ("Lower Head",  "mdi:arrow-down-box"),
}

# Module-level registry so button.py and select.py can stop all movement
_position_switches: list["XPositionSwitch"] = []


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, add_entities: AddEntitiesCallback
):
    device = hass.data[DOMAIN][config_entry.entry_id]
    switches = [XPositionSwitch(device, attr) for attr in POSITION_ATTRS]
    _position_switches.clear()
    _position_switches.extend(switches)
    add_entities(switches)


class XPositionSwitch(XEntity, SwitchEntity):
    _attr_is_on = False

    def __init__(self, device, attr: str):
        super().__init__(device, attr)
        name, icon = POSITION_ATTRS[attr]
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = device.mac.replace(":", "") + "_" + attr
        self.entity_id = (DOMAIN + "." + self._attr_unique_id).lower()
        self._task: asyncio.Task | None = None

    async def async_turn_on(self, **kwargs) -> None:
        # Stop all other position switches first
        for sw in _position_switches:
            if sw is not self and sw._attr_is_on:
                await sw.async_turn_off()

        self._attr_is_on = True
        self._async_write_ha_state()
        self._task = asyncio.create_task(self._move_loop())

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self._async_write_ha_state()
        if self._task:
            self._task.cancel()
            self._task = None

    async def _move_loop(self):
        deadline = asyncio.get_event_loop().time() + POSITION_MAX_DURATION
        try:
            while self._attr_is_on and asyncio.get_event_loop().time() < deadline:
                if self.device.connected:
                    self.device.set_attribute(self.attr, 1)
                    await asyncio.sleep(POSITION_SEND_INTERVAL)
                else:
                    # Not connected — ping to trigger reconnect and wait
                    self.device.client.ping()
                    await asyncio.sleep(RECONNECT_WAIT_INTERVAL)
        except asyncio.CancelledError:
            pass
        finally:
            # Safety cutoff reached or task cancelled — reset to off
            self._attr_is_on = False
            self._async_write_ha_state()