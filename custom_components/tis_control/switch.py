"""TIS relay channels that are not lights (sockets, pumps, valves)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TISConfigEntry
from .const import KIND_SWITCH
from .entity import TISEntity

# Commands are single UDP datagrams and state is pushed, so nothing needs throttling.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: TISConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities(
        TISSwitch(hub, entry.entry_id, spec) for spec in hub.devices if spec["type"] == KIND_SWITCH
    )


class TISSwitch(TISEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        level = self.hub.channels.get((*self.address, self.spec["channel"]))
        return None if level is None else level > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set(100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set(0)

    def _set(self, level: int) -> None:
        self.hub.gateway.set_channel(*self.address, self.spec["channel"], level)
        self.hub.channels[(*self.address, self.spec["channel"])] = level
        self.async_write_ha_state()
