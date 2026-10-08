"""Config flow: gateway address, then the devices (found on the bus, or a TIS Studio export)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tis_smartbus import DEFAULT_PORT, DiscoveredDevice, TISConnectionError, TISGateway
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .const import CONF_DEVICES, CONF_STUDIO_JSON, DISCOVERY_TIMEOUT, DOMAIN
from .device_list import InvalidDeviceList, from_discovery, from_studio_json, has_outputs

_LOGGER = logging.getLogger(__name__)


class TISConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host = ""
        self._port = DEFAULT_PORT
        self._found: list[DiscoveredDevice] = []
        self._channel_counts: dict[tuple[int, int], int] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            self._port = user_input[CONF_PORT]
            # raise_on_progress=False: a setup someone walked away from must not block a new one.
            await self.async_set_unique_id(f"{self._host}:{self._port}", raise_on_progress=False)
            self._abort_if_unique_id_configured()
            gateway = TISGateway(self._host, self._port)
            try:
                await gateway.connect()
                self._found = await gateway.discover(DISCOVERY_TIMEOUT)
                await self._count_channels(gateway)
            except TISConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error talking to the TIS gateway")
                errors["base"] = "unknown"
            finally:
                await gateway.close()
            if not errors and not self._found:
                errors["base"] = "no_devices"
            if not errors:
                return await self.async_step_source()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Required(CONF_PORT, default=self._port): int,
                }
            ),
            errors=errors,
        )

    async def async_step_source(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="source",
            menu_options=["discovered", "studio"],
            description_placeholders={"count": str(len(self._found))},
        )

    async def async_step_discovered(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        devices = from_discovery(self._found, self._channel_counts)
        if not devices:
            return self.async_abort(reason="nothing_controllable")
        return self._create(devices)

    async def async_step_studio(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                devices = from_studio_json(user_input[CONF_STUDIO_JSON])
            except InvalidDeviceList as err:
                _LOGGER.debug("Studio export rejected: %s", err)
                errors["base"] = "invalid_studio_json"
            else:
                return self._create(devices)
        return self.async_show_form(
            step_id="studio",
            data_schema=vol.Schema(
                {vol.Required(CONF_STUDIO_JSON): TextSelector(TextSelectorConfig(multiline=True))}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Point an existing entry at a different gateway (new IP after a router change, etc.)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), user_input[CONF_PORT]
            unique_id = f"{host}:{port}"
            if unique_id != entry.unique_id:
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
            gateway = TISGateway(host, port)
            try:
                await gateway.connect()
                heard = await gateway.discover(DISCOVERY_TIMEOUT / 2)
            except TISConnectionError:
                errors["base"] = "cannot_connect"
            finally:
                await gateway.close()
            if not errors and not heard:
                errors["base"] = "no_devices"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=unique_id,
                    title=f"TIS gateway {host}",
                    data_updates={CONF_HOST: host, CONF_PORT: port},
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): int,
                }
            ),
            errors=errors,
        )

    async def _count_channels(self, gateway: TISGateway) -> None:
        """Ask each output module how many channels it has (read-only)."""
        modules = [m for m in self._found if has_outputs(m)]
        replies = await asyncio.gather(*(gateway.read_channels(m.subnet, m.device) for m in modules))
        self._channel_counts = {
            m.address: len(levels) for m, levels in zip(modules, replies, strict=True) if levels
        }

    def _create(self, devices: list[dict[str, Any]]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=f"TIS gateway {self._host}",
            data={CONF_HOST: self._host, CONF_PORT: self._port, CONF_DEVICES: devices},
        )
