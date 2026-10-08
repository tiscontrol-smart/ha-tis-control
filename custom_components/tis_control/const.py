"""Constants for TIS Control."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "tis_control"

CONF_DEVICES = "devices"
CONF_STUDIO_JSON = "studio_json"

POLL_INTERVAL = timedelta(seconds=30)
# Long enough to also catch modules that only show up through their own periodic broadcasts.
DISCOVERY_TIMEOUT = 8.0

# Entity kinds in a device list (same names as TIS Studio's Home Assistant export).
KIND_LIGHT = "light"
KIND_SWITCH = "switch"
KIND_COVER = "cover"
KIND_CLIMATE = "climate"
KIND_SCENE = "scene"
KINDS = (KIND_LIGHT, KIND_SWITCH, KIND_COVER, KIND_CLIMATE, KIND_SCENE)
