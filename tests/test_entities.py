"""Setup, entities and live bus updates."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry
from tis_smartbus import OpCode

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.tis_control.const import CONF_DEVICES, DOMAIN

DEVICES = [
    {"id": "main", "name": "Main", "module": "Living Dimmer", "type": "light", "subnet": 1, "device": 5,
     "channel": 1, "dimmable": True},
    {"id": "spots", "name": "Spots", "module": "Living Dimmer", "type": "light", "subnet": 1, "device": 5,
     "channel": 2, "dimmable": True},
    {"id": "pump", "name": "Pump", "module": "Living Dimmer", "type": "switch", "subnet": 1, "device": 5, "channel": 3},
    {"id": "curtain", "name": "Curtain", "type": "cover", "subnet": 1, "device": 6, "channel": 1},
    {"id": "movie", "name": "Movie", "type": "scene", "subnet": 1, "device": 8, "area": 1, "scene": 3},
    {"id": "ac", "name": "AC", "module": "Living AC", "type": "climate", "subnet": 1, "device": 10},
    {"id": "hall", "name": "Hall", "type": "light", "subnet": 2, "device": 9, "channel": 1},
]


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="192.168.1.50:6000",
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 6000, CONF_DEVICES: DEVICES},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_unload_and_initial_state(hass: HomeAssistant, fake_gateway) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    main = hass.states.get("light.living_dimmer_main")
    assert main.state == STATE_ON and main.attributes["brightness"] == 255
    assert hass.states.get("light.living_dimmer_spots").state == STATE_OFF
    assert hass.states.get("switch.living_dimmer_pump").state == STATE_ON  # channel 3 at 40 %
    # 2.9 never answers the poll -> unavailable
    assert hass.states.get("light.tis_2_9_hall").state == STATE_UNAVAILABLE
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert fake_gateway.instances[-1].closed


async def test_light_commands_and_push(hass: HomeAssistant, fake_gateway) -> None:
    await _setup(hass)
    gw = fake_gateway.instances[-1]
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: "light.living_dimmer_spots", "brightness": 128, "transition": 2},
        blocking=True,
    )
    assert gw.sent[-1] == ("channel", 1, 5, 2, 50, 2)
    assert hass.states.get("light.living_dimmer_spots").attributes["brightness"] == 128

    # someone presses a wall switch: the module broadcasts channel 1 -> 0
    gw.push((1, 5), OpCode.SINGLE_CHANNEL_REPLY, bytes.fromhex("01f800"))  # live format
    await hass.async_block_till_done()
    assert hass.states.get("light.living_dimmer_main").state == STATE_OFF


async def test_cover_scene_climate(hass: HomeAssistant, fake_gateway) -> None:
    await _setup(hass)
    gw = fake_gateway.instances[-1]
    await hass.services.async_call("cover", "close_cover", {ATTR_ENTITY_ID: "cover.tis_1_6_curtain"}, blocking=True)
    assert gw.sent[-1] == ("curtain", 1, 6, 1, 2)
    await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: "button.tis_1_8_movie"}, blocking=True)
    assert gw.sent[-1] == ("scene", 1, 8, 1, 3)

    climate = "climate.living_ac_ac"
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: climate, "hvac_mode": "cool"}, blocking=True)
    assert gw.sent[-2:] == [("panel", 1, 10, 0x03, 1), ("panel", 1, 10, 0x06, 0)]
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: climate, "temperature": 23}, blocking=True)
    assert gw.sent[-1] == ("panel", 1, 10, 0x04, 23)
    # the wall panel changes the setpoint to 26 (live capture content "041a00")
    gw.push((1, 10), OpCode.PANEL_CONTROL_REPLY, bytes.fromhex("041a00"))
    await hass.async_block_till_done()
    state = hass.states.get(climate)
    assert state.state == "cool" and state.attributes["temperature"] == 26
