"""Base entity for TIS Control."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .hub import TISHub


class TISEntity(Entity):
    """One output (channel, curtain, AC, scene) on one TIS module."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: TISHub, entry_id: str, spec: dict[str, Any]) -> None:
        self.hub = hub
        self.spec = spec
        self.address: tuple[int, int] = (spec["subnet"], spec["device"])
        self._attr_unique_id = f"{entry_id}_{spec['id']}"
        self._attr_name = spec.get("name") or None
        module = spec.get("module") or f"TIS {self.address[0]}.{self.address[1]}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{self.address[0]}_{self.address[1]}")},
            name=module,
            manufacturer="TIS Control",
            model=spec.get("model"),
        )

    @property
    def available(self) -> bool:
        return self.hub.is_online(self.address)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.hub.subscribe(self.address, self.async_write_ha_state))
