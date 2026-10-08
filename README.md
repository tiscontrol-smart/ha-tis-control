# TIS Control for Home Assistant

Control your **TIS Control** smart-building system from Home Assistant — locally, with no cloud.

Lights, dimmers, relays, curtains, air-conditioning and scenes on the TIS bus show up as Home Assistant
devices, and changes made anywhere (wall switches, panels, the TIS app) appear instantly.

## Requirements

- A TIS installation with at least one **TIS IP gateway** (IP-COM-PORT, GTY, or an RCU with IP) on the
  same network as Home Assistant.
- Home Assistant 2025.6 or newer. Home Assistant needs to receive UDP broadcasts on port **6000** from the
  gateway — on Home Assistant OS and a Docker container with host networking this works out of the box.

## Install

**With HACS** (recommended): HACS → ⋮ → *Custom repositories* → add
`https://github.com/tiscontrol-smart/ha-tis-control` as an *Integration* → install **TIS Control** →
restart Home Assistant.

**Manually**: copy `custom_components/tis_control` into your Home Assistant `config/custom_components/`
folder and restart.

## Set up

1. **Settings → Devices & services → Add integration → TIS Control.**
2. Enter the IP address of any TIS IP gateway. Home Assistant asks every module on the network to
   identify itself (read-only — nothing is switched).
3. Choose:
   - **Add the modules that were found** — dimmers become dimmable lights, relay modules become
     switches, HVAC modules become climate entities; or
   - **Import from TIS Studio** — paste the `devices.json` from TIS Studio (*Configuration → Home
     Assistant*) to get your real room and channel names, curtains and scenes.

Sites with several IP gateways are handled automatically: the integration learns which gateway each
module sits behind and sends commands there.

To change the gateway address later: **TIS Control → ⋮ → Reconfigure**.

## Supported

| TIS | Home Assistant |
|---|---|
| Dimmer channels (DIM-…, DMX) | Light with brightness and fade |
| Relay channels (RLY-…, RCU-…) | Switch (use *Show as → Light* for lighting) |
| Curtain channels | Cover: open / close / stop |
| AC / HVAC panels | Climate: power, mode, fan, setpoint |
| Scenes | Button |

## Known limitations

- Curtain position is not reported by the modules; the cover shows the last command.
- AC values appear once they have been changed or broadcast on the bus at least once.
- Sensors, security, audio and dry contacts are not supported yet.

## Removing

**Settings → Devices & services → TIS Control → ⋮ → Delete**, then remove it in HACS if you installed it
there.

## Troubleshooting

- **No modules answered**: check the gateway IP, and that Home Assistant is on the same network and can
  receive UDP port 6000 (Docker: use host networking).
- **A module shows unavailable**: it stopped answering status reads. Check its bus connection; it comes
  back by itself.
- **Download diagnostics** (TIS Control → ⋮) and attach the file when opening an issue.

## How it works

The integration uses [tis-smartbus](https://github.com/tiscontrol-smart/tis-smartbus), an async Python
library for the TIS SmartBus over UDP. Everything stays on your local network.

## License

Apache-2.0 © TIS Control
