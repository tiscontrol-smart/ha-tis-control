"""Fixtures: a fake TIS bus, so no hardware (and no UDP port 6000) is needed."""

from __future__ import annotations

from collections.abc import Callable, Generator
from unittest.mock import patch

import pytest
from tis_smartbus import DiscoveredDevice, OpCode, Telegram, lookup

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    return


class FakeGateway:
    """Stands in for tis_smartbus.TISGateway: one DIM-6CH-2A at 1.5 and one HVAC at 1.10."""

    instances: list[FakeGateway] = []
    fail_connect = False
    modules: list[DiscoveredDevice] = []

    def __init__(self, host: str, port: int = 6000, **_: object) -> None:
        self.host, self.port = host, port
        self.local_ip = "192.168.1.200"
        self.sent: list[tuple] = []
        self.levels = {(1, 5): [100, 0, 40, 0, 0, 0], (4, 200): [0] * 20}
        self.listeners: list[Callable[[Telegram], None]] = []
        self.closed = False
        FakeGateway.instances.append(self)

    async def connect(self) -> None:
        from tis_smartbus import TISConnectionError

        if FakeGateway.fail_connect:
            raise TISConnectionError("boom")

    async def close(self) -> None:
        self.closed = True

    def add_listener(self, listener: Callable[[Telegram], None]) -> Callable[[], None]:
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    async def discover(self, timeout: float = 3.0) -> list[DiscoveredDevice]:
        return list(FakeGateway.modules)

    async def read_channels(self, subnet: int, device: int, timeout: float = 2.0) -> list[int] | None:
        return self.levels.get((subnet, device))

    def set_channel(self, subnet: int, device: int, channel: int, level: int, ramp_seconds: int = 0) -> None:
        self.sent.append(("channel", subnet, device, channel, level, ramp_seconds))

    def run_scene(self, subnet: int, device: int, area: int, number: int) -> None:
        self.sent.append(("scene", subnet, device, area, number))

    def curtain(self, subnet: int, device: int, channel: int, action) -> None:
        self.sent.append(("curtain", subnet, device, channel, int(action)))

    def panel(self, subnet: int, device: int, kind, value: int) -> None:
        self.sent.append(("panel", subnet, device, int(kind), value))

    def push(self, src: tuple[int, int], opcode: int, content: bytes) -> None:
        """Simulate a telegram heard on the bus."""
        tel = Telegram(src[0], src[1], 0x0258, opcode, 255, 255, content, True)
        for listener in list(self.listeners):
            listener(tel)


@pytest.fixture
def fake_gateway() -> Generator[type[FakeGateway]]:
    FakeGateway.instances = []
    FakeGateway.fail_connect = False
    FakeGateway.modules = [
        DiscoveredDevice(1, 5, lookup(0x0258), "Living Dimmer"),
        DiscoveredDevice(1, 10, lookup(0x0077), ""),
        DiscoveredDevice(4, 200, lookup(0x802D), "Plant Room RCU"),
    ]
    with (
        patch("custom_components.tis_control.TISGateway", FakeGateway),
        patch("custom_components.tis_control.config_flow.TISGateway", FakeGateway),
    ):
        yield FakeGateway


__all__ = ["FakeGateway", "OpCode"]
