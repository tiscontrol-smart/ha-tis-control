"""TIS curtain / shutter channels."""

from __future__ import annotations

from typing import Any

from tis_smartbus import CurtainAction

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TISConfigEntry
from .const import KIND_COVER
from .entity import TISEntity

# Commands are single UDP datagrams and state is pushed, so nothing needs throttling.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: TISConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities(
        TISCover(hub, entry.entry_id, spec) for spec in hub.devices if spec["type"] == KIND_COVER
    )


class TISCover(TISEntity, CoverEntity):
    """Open / close / stop. Position feedback has no confirmed byte layout yet, so state is assumed."""

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_is_closed: bool | None = None

    async def async_open_cover(self, **kwargs: Any) -> None:
        self._send(CurtainAction.OPEN, closed=False)

    async def async_close_cover(self, **kwargs: Any) -> None:
        self._send(CurtainAction.CLOSE, closed=True)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        self._send(CurtainAction.STOP, closed=self._attr_is_closed)

    def _send(self, action: CurtainAction, closed: bool | None) -> None:
        self.hub.gateway.curtain(*self.address, self.spec["channel"], action)
        self._attr_is_closed = closed
        self.async_write_ha_state()
