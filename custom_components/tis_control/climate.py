"""TIS AC / HVAC control through the panel-control opcodes."""

from __future__ import annotations

from typing import Any

from tis_smartbus import AcMode, FanSpeed, PanelType

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TISConfigEntry
from .const import KIND_CLIMATE
from .entity import TISEntity

# Commands are single UDP datagrams and state is pushed, so nothing needs throttling.
PARALLEL_UPDATES = 0

MODE_TO_HA = {
    AcMode.COOL: HVACMode.COOL,
    AcMode.HEAT: HVACMode.HEAT,
    AcMode.FAN: HVACMode.FAN_ONLY,
    AcMode.AUTO: HVACMode.HEAT_COOL,
}
HA_TO_MODE = {v: k for k, v in MODE_TO_HA.items()}
FAN_TO_HA = {FanSpeed.AUTO: FAN_AUTO, FanSpeed.LOW: FAN_LOW, FanSpeed.MEDIUM: FAN_MEDIUM, FanSpeed.HIGH: FAN_HIGH}
HA_TO_FAN = {v: k for k, v in FAN_TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: TISConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities(
        TISClimate(hub, entry.entry_id, spec) for spec in hub.devices if spec["type"] == KIND_CLIMATE
    )


class TISClimate(TISEntity, ClimateEntity):
    """State comes from the AC panel broadcasts, which carry one field per telegram.

    Until a field has been heard on the bus it shows as unknown; every command we send updates the
    field we changed so the card stays in step.
    """

    _attr_hvac_modes = [HVACMode.OFF, *MODE_TO_HA.values()]
    _attr_fan_modes = list(FAN_TO_HA.values())
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self._attr_min_temp = self.spec.get("minTemp", 16)
        self._attr_max_temp = self.spec.get("maxTemp", 30)

    @property
    def _state(self) -> dict[PanelType, int]:
        return self.hub.panels[self.address]

    @property
    def hvac_mode(self) -> HVACMode | None:
        power = self._state.get(PanelType.AC_POWER)
        if power is None:
            return None
        if not power:
            return HVACMode.OFF
        try:
            return MODE_TO_HA[AcMode(self._state.get(PanelType.MODE, AcMode.COOL))]
        except ValueError:
            return HVACMode.COOL

    @property
    def fan_mode(self) -> str | None:
        fan = self._state.get(PanelType.FAN_SPEED)
        try:
            return None if fan is None else FAN_TO_HA[FanSpeed(fan)]
        except ValueError:
            return None

    @property
    def target_temperature(self) -> float | None:
        kind = PanelType.HEAT_SETPOINT if self.hvac_mode == HVACMode.HEAT else PanelType.COOL_SETPOINT
        return self._state.get(kind)

    def _send(self, kind: PanelType, value: int) -> None:
        self.hub.gateway.panel(*self.address, kind, value)
        self._state[kind] = value

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            self._send(PanelType.AC_POWER, 0)
        else:
            self._send(PanelType.AC_POWER, 1)
            self._send(PanelType.MODE, HA_TO_MODE[hvac_mode])
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        self._send(PanelType.AC_POWER, 1)
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        self._send(PanelType.AC_POWER, 0)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._send(PanelType.FAN_SPEED, HA_TO_FAN[fan_mode])
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        kind = PanelType.HEAT_SETPOINT if self.hvac_mode == HVACMode.HEAT else PanelType.COOL_SETPOINT
        self._send(kind, round(temp))
        self.async_write_ha_state()
