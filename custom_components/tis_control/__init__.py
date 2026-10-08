"""The TIS Control integration: TIS SmartBus lighting, curtains, AC and scenes, locally."""

from __future__ import annotations

from tis_smartbus import TISConnectionError, TISGateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICES
from .hub import TISHub

PLATFORMS = [Platform.BUTTON, Platform.CLIMATE, Platform.COVER, Platform.LIGHT, Platform.SWITCH]

type TISConfigEntry = ConfigEntry[TISHub]


async def async_setup_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    gateway = TISGateway(entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        await gateway.connect()
    except TISConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err
    hub = TISHub(hass, gateway, entry.data[CONF_DEVICES])
    await hub.async_start()
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
