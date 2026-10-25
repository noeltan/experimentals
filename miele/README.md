# miele

Experiment: our own controller for Miele connected appliances, so we don't depend on the Miele app.

## Two ways in

### 1. Miele's official cloud API (easiest, if the devices are online)
- Developer portal: https://www.miele.com/developer/ (free client ID and secret).
- REST endpoints plus a Server-Sent Events stream for live status: program, phase, time remaining, temperatures, door state.
- Some actions too, depending on the model: start/stop/pause, power on/off, light, and remote start where the appliance allows it.
- **Catch:** an appliance only shows up here after it has joined Wi-Fi and been linked to a Miele account. That linking is normally done in the app.

### 2. Talk to the appliances directly on the LAN (no cloud)
- Appliances with Miele's Wi-Fi module (XKM 3100W and built-in equivalents) run a small HTTP server on the local network.
- Payloads are encrypted and signed with a group ID and key that are set when the device is "commissioned".
- Community projects have reverse-engineered both commissioning and the local API (search "MieleRESTServer" and "miele local api"). That would let us:
  1. put the appliance into Wi-Fi setup / "app connection" mode, so it opens its own access point,
  2. send it our home Wi-Fi details and our own group key,
  3. then poll it and control it from our own code.
- **Catch:** unofficial, so it varies by model and firmware, and it can break.

## Plan (to be confirmed)
1. Work out where things fail: the device never joins Wi-Fi, or it joins but the app can't see or control it.
2. If any device is online: start with the cloud API (a small script that lists devices and streams their status).
3. If none will onboard: try LAN commissioning on one appliance.
4. Wrap whichever works in a simple dashboard (and/or Home Assistant).

## Devices
| Appliance | Model | Wi-Fi status | Notes |
|-----------|-------|--------------|-------|
| _tbd_     |       |              |       |
