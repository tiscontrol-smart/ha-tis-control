"""TIS dimmer and relay channels as lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TISConfigEntry
from .const import KIND_LIGHT
from .entity import TISEntity

# Commands are single UDP datagrams and state is pushed, so nothing needs throttling.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: TISConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities(
        TISLight(hub, entry.entry_id, spec) for spec in hub.devices if spec["type"] == KIND_LIGHT
    )


def _to_ha(level: int) -> int:
    return round(level * 255 / 100)


def _to_tis(brightness: int) -> int:
    return max(1, round(brightness * 100 / 255))


class TISLight(TISEntity, LightEntity):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self._channel: int = self.spec["channel"]
        if self.spec.get("dimmable"):
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_features = LightEntityFeature.TRANSITION
        else:
            self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {self._attr_color_mode}
        self._last_on_level = 100

    @property
    def _level(self) -> int | None:
        return self.hub.channels.get((*self.address, self._channel))

    @property
    def is_on(self) -> bool | None:
        level = self._level
        return None if level is None else level > 0

    @property
    def brightness(self) -> int | None:
        level = self._level
        if level is None or self._attr_color_mode is ColorMode.ONOFF:
            return None
        if level > 0:
            self._last_on_level = level
        return _to_ha(level)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs and self._attr_color_mode is ColorMode.BRIGHTNESS:
            level = _to_tis(kwargs[ATTR_BRIGHTNESS])
        elif self._attr_color_mode is ColorMode.BRIGHTNESS:
            level = self._last_on_level
        else:
            level = 100
        self._set(level, kwargs.get(ATTR_TRANSITION))

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set(0, kwargs.get(ATTR_TRANSITION))

    def _set(self, level: int, transition: float | None) -> None:
        self.hub.gateway.set_channel(*self.address, self._channel, level, round(transition or 0))
        # The module confirms with a 0x0032 reply; show the new state now so the UI does not lag.
        self.hub.channels[(*self.address, self._channel)] = level
        self.async_write_ha_state()
