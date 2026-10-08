"""Diagnostics download for TIS Control."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import TISConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: TISConfigEntry) -> dict[str, Any]:
    hub = entry.runtime_data
    return {
        "gateway": {"host": entry.data["host"], "port": entry.data["port"], "local_ip": hub.gateway.local_ip},
        "devices": entry.data["devices"],
        "online": {f"{s}.{d}": ok for (s, d), ok in hub.online.items()},
        "channels": {f"{s}.{d}.{c}": lvl for (s, d, c), lvl in hub.channels.items()},
        "panels": {f"{s}.{d}": {k.name: v for k, v in st.items()} for (s, d), st in hub.panels.items()},
    }
