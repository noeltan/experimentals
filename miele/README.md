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

## Status
Going with option 1, the cloud API. `miele.py` is a small command-line client that needs only standard Python 3.

### Step 0: get each appliance into the Miele app once
The cloud API can only see appliances that are already on your Miele account, so each one has to make it through the app's setup one time. After that we don't need the app. If the app's setup keeps failing:
- **Use 2.4 GHz Wi-Fi.** Most Miele Wi-Fi modules can't use 5 GHz. If your router or mesh puts both bands under one network name, temporarily turn on a separate 2.4 GHz network, or turn off "band steering", just while you do the setup.
- **Try WPS instead of the app's Wi-Fi handoff.** On the appliance, go to *Settings → Miele@home → Log in via WPS*, then press the WPS button on your router within 2 minutes. Once the appliance is on Wi-Fi, open the app's *Add appliance* screen on the same network so it can find the appliance.
- Allow the app location and local-network permissions on your phone. Also turn off your phone's VPN, Private Relay and "switch to mobile data" during setup.
- Stand near the router. Appliances in a garage or laundry often have a weak signal.

### Step 1: developer credentials (free)
Sign up at https://developer.miele.com → *Get involved*. You'll get a client ID and secret. If the form asks for a redirect URI, give it `http://localhost:8080/callback`.

```sh
export MIELE_CLIENT_ID=...
export MIELE_CLIENT_SECRET=...
```

### Step 2: use it
```sh
python3 miele.py login                    # opens the Miele sign-in page, saves tokens to .tokens.json (git-ignored)
python3 miele.py devices                  # appliances + status
python3 miele.py watch                    # live updates
python3 miele.py actions <device-id>      # what it accepts right now
python3 miele.py do <device-id> start     # start | stop | pause | on | off | light-on | light-off
```
Starting a program remotely only works if *Remote Start* / *Mobile Start* is switched on at the appliance and the appliance is ready to go (door closed, detergent in, and so on). This is Miele's safety rule; the API can't get around it.

Optional settings: `MIELE_LANGUAGE` (default `en`), `MIELE_REDIRECT_URI`, `MIELE_TOKEN_FILE`.

### Next
- A phone-friendly web dashboard on top of this.
- Fallback: option 2 (local LAN) for any appliance that just won't join through the app.

## Devices
| Appliance | Model | Wi-Fi status | Notes |
|-----------|-------|--------------|-------|
| _tbd_     |       |              |       |
