"""Config flow tests."""

from __future__ import annotations

import json

from tis_smartbus import DiscoveredDevice, lookup

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.tis_control.const import CONF_DEVICES, DOMAIN

STUDIO_EXPORT = {
    "gatewayIp": "192.168.1.50",
    "devices": [
        {"id": "living_main", "name": "Living Main", "deviceName": "Living Relay", "type": "light",
         "subnet": 1, "device": 5, "channel": 1, "dimmable": True},
        {"id": "curtain", "name": "Curtain", "type": "cover", "subnet": 1, "device": 6, "channel": 1},
        {"id": "movie", "name": "Movie", "type": "scene", "subnet": 1, "device": 8, "area": 1, "scene": 3},
        {"id": "ac", "name": "AC", "type": "climate", "subnet": 1, "device": 10},
        {"id": "ignored", "type": "doorbell", "subnet": 1, "device": 9},
    ],
}


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.50", CONF_PORT: 6000}
    )


async def test_discovered_devices(hass: HomeAssistant, fake_gateway) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["description_placeholders"] == {"count": "3"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "discovered"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    devices = result["data"][CONF_DEVICES]
    # 6 dimmer channels, 20 RCU relays (count read from the module), 1 AC
    assert [d["type"] for d in devices].count("light") == 6
    rcu = [d for d in devices if d["module"] == "Plant Room RCU"]
    assert len(rcu) == 20 and {d["type"] for d in rcu} == {"switch"}
    assert devices[0]["module"] == "Living Dimmer" and devices[0]["dimmable"] is True
    assert any(d["type"] == "climate" for d in devices)
    assert fake_gateway.instances[0].closed  # the discovery connection; the entry then opens its own


async def test_studio_import(hass: HomeAssistant, fake_gateway) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "studio"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"studio_json": "nope"})
    assert result["errors"] == {"base": "invalid_studio_json"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"studio_json": json.dumps(STUDIO_EXPORT)}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [d["id"] for d in result["data"][CONF_DEVICES]] == ["living_main", "curtain", "movie", "ac"]


async def test_cannot_connect_then_recover(hass: HomeAssistant, fake_gateway) -> None:
    fake_gateway.fail_connect = True
    result = await _start(hass)
    assert result["errors"] == {"base": "cannot_connect"}
    fake_gateway.fail_connect = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.50", CONF_PORT: 6000}
    )
    assert result["type"] is FlowResultType.MENU


async def test_no_devices(hass: HomeAssistant, fake_gateway) -> None:
    fake_gateway.modules = []
    result = await _start(hass)
    assert result["errors"] == {"base": "no_devices"}


async def test_already_configured(hass: HomeAssistant, fake_gateway) -> None:
    result = await _start(hass)
    await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "discovered"})
    result = await _start(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abandoned_flow_does_not_block_a_new_one(hass: HomeAssistant, fake_gateway) -> None:
    """Field test: someone closed the dialog at the menu, then started again."""
    first = await _start(hass)
    assert first["type"] is FlowResultType.MENU
    second = await _start(hass)
    assert second["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(second["flow_id"], {"next_step_id": "discovered"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_changes_the_gateway(hass: HomeAssistant, fake_gateway) -> None:
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "discovered"})
    entry = result["result"]
    await hass.async_block_till_done()
    devices_before = entry.data[CONF_DEVICES]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    fake_gateway.modules = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.60", CONF_PORT: 6000}
    )
    assert result["errors"] == {"base": "no_devices"}
    fake_gateway.modules = [DiscoveredDevice(1, 5, lookup(0x0258), "Living Dimmer")]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.60", CONF_PORT: 6000}
    )
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.60" and entry.unique_id == "192.168.1.60:6000"
    assert entry.data[CONF_DEVICES] == devices_before
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
