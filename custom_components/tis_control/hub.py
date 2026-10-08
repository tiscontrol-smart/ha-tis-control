"""Live bus state shared by all TIS entities of one config entry."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from tis_smartbus import OpCode, PanelType, Telegram, TISGateway
from tis_smartbus import commands as cmd

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import KIND_LIGHT, KIND_SWITCH, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

Address = tuple[int, int]


class TISHub:
    """Listens to every telegram, keeps the last known state and tells entities when it changes.

    The bus pushes most changes (a wall switch, a scene, another app). Modules with output channels are
    also polled every POLL_INTERVAL so a missed broadcast heals itself; a module that stops answering is
    reported unavailable.
    """

    def __init__(self, hass: HomeAssistant, gateway: TISGateway, devices: list[dict[str, Any]]) -> None:
        self.hass = hass
        self.gateway = gateway
        self.devices = devices
        self.channels: dict[tuple[int, int, int], int] = {}
        self.panels: dict[Address, dict[PanelType, int]] = defaultdict(dict)
        self.online: dict[Address, bool] = {}
        self._subscribers: dict[Address, list[Callable[[], None]]] = defaultdict(list)
        self._unsubs: list[CALLBACK_TYPE] = []
        # Only modules with lighting/relay outputs answer a channel-status read; curtain, AC and scene
        # modules do not, and polling them would wrongly mark them unavailable.
        self._poll_targets: set[Address] = {
            (d["subnet"], d["device"]) for d in devices if d["type"] in (KIND_LIGHT, KIND_SWITCH)
        }

    async def async_start(self) -> None:
        self._unsubs.append(self.gateway.add_listener(self._on_telegram))
        self._unsubs.append(
            async_track_time_interval(self.hass, self._async_poll, POLL_INTERVAL)
        )
        await self._async_poll()

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self.gateway.close()

    @callback
    def subscribe(self, address: Address, update: Callable[[], None]) -> CALLBACK_TYPE:
        self._subscribers[address].append(update)
        return lambda: self._subscribers[address].remove(update)

    def is_online(self, address: Address) -> bool:
        return self.online.get(address, True)

    async def _async_poll(self, _now: datetime | None = None) -> None:
        targets = sorted(self._poll_targets)
        results = await asyncio.gather(*(self.gateway.read_channels(*a) for a in targets))
        for address, levels in zip(targets, results, strict=True):
            was = self.online.get(address)
            self.online[address] = levels is not None
            if levels is None:
                if was is not False:
                    _LOGGER.info("TIS module %s.%s is not answering", *address)
                    self._notify(address)
                continue
            if was is False:
                _LOGGER.info("TIS module %s.%s is back", *address)
            for ch, level in enumerate(levels, start=1):
                self.channels[(*address, ch)] = level
            self._notify(address)

    @callback
    def _on_telegram(self, tel: Telegram) -> None:
        address = tel.source
        changed = False
        for item in cmd.decode_channel_levels(tel.opcode, tel.content):
            self.channels[(*address, item.channel)] = item.level
            changed = True
        if tel.opcode == OpCode.PANEL_CONTROL_REPLY:
            field = cmd.decode_panel(tel.content)
            if field is not None:
                self.panels[address][field[0]] = field[1]
                changed = True
        if changed:
            self.online[address] = True
            self._notify(address)

    @callback
    def _notify(self, address: Address) -> None:
        for update in list(self._subscribers.get(address, ())):
            update()
