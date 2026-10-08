"""Turn discovery results or a TIS Studio export into the stored device list.

Each entry is a plain dict (it is stored in the config entry)::

    {"id", "name", "type", "subnet", "device", "channel"?, "dimmable"?, "area"?, "scene"?,
     "module"?, "model"?}

``type`` is one of const.KINDS; ``module`` names the physical TIS module the entity sits on.
"""

from __future__ import annotations

import json
from typing import Any

from tis_smartbus import Category, DiscoveredDevice

from .const import KIND_CLIMATE, KIND_LIGHT, KIND_SCENE, KIND_SWITCH, KINDS


class InvalidDeviceList(ValueError):
    """The pasted Studio export could not be used."""


def has_outputs(mod: DiscoveredDevice) -> bool:
    return mod.device_type.category in (Category.DIMMER, Category.RELAY)


def from_discovery(
    found: list[DiscoveredDevice], channel_counts: dict[tuple[int, int], int] | None = None
) -> list[dict[str, Any]]:
    """Entities for every module whose outputs we can infer from its type.

    ``channel_counts`` comes from asking each output module how many channels it has; it wins over
    the device-type table, which does not know every model.
    """
    channel_counts = channel_counts or {}
    out: list[dict[str, Any]] = []
    for mod in found:
        dtype = mod.device_type
        module = mod.name or f"{dtype.model} {mod.subnet}.{mod.device}"
        common = {"subnet": mod.subnet, "device": mod.device, "module": module, "model": dtype.model}
        channels = channel_counts.get(mod.address) or dtype.channels
        if has_outputs(mod) and channels:
            dimmable = dtype.category is Category.DIMMER
            for ch in range(1, channels + 1):
                out.append({
                    **common,
                    "id": f"{mod.subnet}_{mod.device}_{ch}",
                    "name": f"Channel {ch}",
                    "type": KIND_LIGHT if dimmable else KIND_SWITCH,
                    "channel": ch,
                    "dimmable": dimmable,
                })
        elif dtype.category is Category.HVAC:
            out.append({**common, "id": f"{mod.subnet}_{mod.device}_ac", "name": "Air conditioner",
                        "type": KIND_CLIMATE})
    return out


def _int(entry: dict[str, Any], key: str, lo: int, hi: int) -> int:
    try:
        value = int(entry[key])
    except (KeyError, TypeError, ValueError) as err:
        raise InvalidDeviceList(f"{entry.get('name') or entry.get('id')}: missing {key}") from err
    if not lo <= value <= hi:
        raise InvalidDeviceList(f"{entry.get('name') or entry.get('id')}: {key} out of range")
    return value


def from_studio_json(text: str) -> list[dict[str, Any]]:
    """Parse TIS Studio's Home Assistant export (the bridge's devices.json)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        raise InvalidDeviceList("not valid JSON") from err
    items = data.get("devices") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        raise InvalidDeviceList("no devices in the export")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict) or raw.get("type") not in KINDS:
            continue
        entry: dict[str, Any] = {
            "id": str(raw.get("id") or "").strip(),
            "name": str(raw.get("name") or raw.get("id") or "").strip(),
            "type": raw["type"],
            "subnet": _int(raw, "subnet", 1, 254),
            "device": _int(raw, "device", 1, 254),
        }
        if raw.get("deviceName"):
            entry["module"] = str(raw["deviceName"])
        if entry["type"] == KIND_SCENE:
            entry["area"] = _int({**raw, "area": raw.get("area", 1)}, "area", 0, 255)
            entry["scene"] = _int({**raw, "scene": raw.get("scene", 1)}, "scene", 0, 255)
        elif entry["type"] != KIND_CLIMATE:
            entry["channel"] = _int(raw, "channel", 1, 255)
            entry["dimmable"] = bool(raw.get("dimmable"))
        if not entry["id"]:
            entry["id"] = f"{entry['subnet']}_{entry['device']}_{entry.get('channel', entry['type'])}"
        if entry["id"] in seen:
            continue
        seen.add(entry["id"])
        out.append(entry)
    if not out:
        raise InvalidDeviceList("no supported devices in the export")
    return out
