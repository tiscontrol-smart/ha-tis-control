"""TIS scenes as buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TISConfigEntry
from .const import KIND_SCENE
from .entity import TISEntity

# Commands are single UDP datagrams and state is pushed, so nothing needs throttling.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: TISConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities(
        TISScene(hub, entry.entry_id, spec) for spec in hub.devices if spec["type"] == KIND_SCENE
    )


class TISScene(TISEntity, ButtonEntity):
    @property
    def available(self) -> bool:
        return True  # a scene module is not polled; firing is fire-and-forget

    async def async_press(self) -> None:
        self.hub.gateway.run_scene(*self.address, self.spec.get("area", 1), self.spec.get("scene", 1))
