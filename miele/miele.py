#!/usr/bin/env python3
"""Small command-line client for the Miele 3rd Party (cloud) API.

Standard library only. Credentials come from the Miele developer portal
(https://developer.miele.com, "Get involved") and are read from the
MIELE_CLIENT_ID and MIELE_CLIENT_SECRET environment variables.

    python3 miele.py login                  # one-time browser sign-in
    python3 miele.py devices                # list appliances and their status
    python3 miele.py watch                  # live status updates (Ctrl+C to stop)
    python3 miele.py actions <device-id>    # what the appliance accepts right now
    python3 miele.py do <device-id> <cmd>   # start | stop | pause | on | off | light-on | light-off
"""

import argparse
import http.server
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

AUTH_URL = "https://auth.domestic.miele-iot.com/partner/realms/mcs/protocol/openid-connect/auth"
TOKEN_URL = "https://auth.domestic.miele-iot.com/partner/realms/mcs/protocol/openid-connect/token"
API = "https://api.mcs3.miele.com/v1"

TOKEN_FILE = Path(os.environ.get("MIELE_TOKEN_FILE", Path(__file__).with_name(".tokens.json")))
REDIRECT_URI = os.environ.get("MIELE_REDIRECT_URI", "http://localhost:8080/callback")
LANGUAGE = os.environ.get("MIELE_LANGUAGE", "en")

# Body sent to PUT /devices/{id}/actions for each command. The key is also
# what GET /devices/{id}/actions reports, so we can check it is allowed first.
COMMANDS = {
    "start": ("processAction", 1),
    "stop": ("processAction", 2),
    "pause": ("processAction", 3),
    "on": ("powerOn", True),
    "off": ("powerOff", True),
    "light-on": ("light", 1),
    "light-off": ("light", 2),
}


def die(msg):
    sys.exit(f"error: {msg}")


def client_credentials():
    cid, secret = os.environ.get("MIELE_CLIENT_ID"), os.environ.get("MIELE_CLIENT_SECRET")
    if not cid or not secret:
        die("set MIELE_CLIENT_ID and MIELE_CLIENT_SECRET (from developer.miele.com)")
    return cid, secret


# --- tokens -------------------------------------------------------------------

def save_tokens(tok):
    tok["expires_at"] = time.time() + int(tok.get("expires_in", 0))
    TOKEN_FILE.write_text(json.dumps(tok, indent=2))
    TOKEN_FILE.chmod(0o600)


def token_request(fields):
    cid, secret = client_credentials()
    body = urllib.parse.urlencode({**fields, "client_id": cid, "client_secret": secret}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        die(f"token request failed ({e.code}): {e.read().decode(errors='replace')}")


def access_token():
    if not TOKEN_FILE.exists():
        die("not signed in yet; run: python3 miele.py login")
    tok = json.loads(TOKEN_FILE.read_text())
    if time.time() > tok.get("expires_at", 0) - 60:
        if not tok.get("refresh_token"):
            die("session expired; run: python3 miele.py login")
        new = token_request({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
        new.setdefault("refresh_token", tok["refresh_token"])
        save_tokens(new)
        tok = new
    return tok["access_token"]


def cmd_login(_args):
    cid, _ = client_credentials()
    state = secrets.token_urlsafe(16)
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT_URI, "state": state,
    })
    redirect = urllib.parse.urlparse(REDIRECT_URI)
    result = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Signed in. You can close this tab and go back to the terminal.")

        def log_message(self, *_):
            pass

    print("Opening the Miele sign-in page. If it doesn't open, visit:\n\n  " + url + "\n")
    webbrowser.open(url)
    server = http.server.HTTPServer((redirect.hostname, redirect.port or 80), Callback)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()

    if "error" in result:
        die(f"sign-in failed: {result.get('error_description', result['error'])}")
    if result.get("state") != state:
        die("sign-in response didn't match this request (state mismatch); try again")
    save_tokens(token_request({"grant_type": "authorization_code", "code": result["code"], "redirect_uri": REDIRECT_URI}))
    print(f"Signed in. Tokens saved to {TOKEN_FILE}")


# --- API ----------------------------------------------------------------------

def api(method, path, body=None):
    sep = "&" if "?" in path else "?"
    req = urllib.request.Request(
        f"{API}{path}{sep}language={LANGUAGE}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {access_token()}", "Accept": "application/json",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        die(f"{method} {path} failed ({e.code}): {e.read().decode(errors='replace')}")


def localized(field):
    return (field or {}).get("value_localized") or ""


def describe(device_id, dev):
    ident, state = dev.get("ident", {}), dev.get("state", {})
    kind = localized(ident.get("type")) or "Appliance"
    name = ident.get("deviceName") or ident.get("deviceIdentLabel", {}).get("techType") or ""
    parts = [localized(state.get("status"))]
    program = localized(state.get("ProgramID"))
    phase = localized(state.get("programPhase"))
    if program:
        parts.append(program + (f" ({phase})" if phase else ""))
    remaining = state.get("remainingTime") or [0, 0]
    if any(remaining):
        parts.append(f"{remaining[0]}h{remaining[1]:02d}m left")
    for t in state.get("temperature") or []:
        if t.get("value_raw") not in (None, -32768):
            parts.append(f"{t['value_raw'] / 100:g}°{'C' if t.get('unit') == 'Celsius' else 'F'}")
            break
    if state.get("signalDoor"):
        parts.append("door open")
    label = f"{kind} {name}".strip()
    return f"{label}  [{device_id}]\n    " + " · ".join(p for p in parts if p)


def cmd_devices(_args):
    devices = api("GET", "/devices") or {}
    if not devices:
        print("No appliances on this Miele account yet. They have to be added in the Miele app first.")
    for device_id, dev in devices.items():
        print(describe(device_id, dev))


def cmd_watch(_args):
    # Server-sent events: "devices" carries the full GET /devices payload on
    # every change, "actions" the allowed actions, "ping" is a 20 s heartbeat.
    while True:
        req = urllib.request.Request(f"{API}/devices/all/events?language={LANGUAGE}", headers={
            "Authorization": f"Bearer {access_token()}", "Accept": "text/event-stream; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                print("Watching for changes (Ctrl+C to stop)...")
                event, data = None, []
                for raw in resp:
                    line = raw.decode().rstrip("\r\n")
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data.append(line[5:].strip())
                    elif not line and event:
                        if event == "devices" and data:
                            print(f"\n--- {time.strftime('%H:%M:%S')}")
                            for device_id, dev in json.loads("\n".join(data)).items():
                                print(describe(device_id, dev))
                        event, data = None, []
        except KeyboardInterrupt:
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"connection dropped ({e}); reconnecting in 5 s", file=sys.stderr)
            time.sleep(5)


def cmd_actions(args):
    print(json.dumps(api("GET", f"/devices/{args.device}/actions"), indent=2))


def cmd_do(args):
    key, value = COMMANDS[args.command]
    allowed = api("GET", f"/devices/{args.device}/actions") or {}
    ok = allowed.get(key)
    if not (value in ok if isinstance(ok, list) else ok):
        die(f"'{args.command}' isn't allowed on this appliance right now "
            "(it may need Remote Start / Mobile Start switched on, or the door closed). "
            f"Allowed now: python3 miele.py actions {args.device}")
    api("PUT", f"/devices/{args.device}/actions", {key: value})
    print(f"Sent '{args.command}'.")


def main():
    p = argparse.ArgumentParser(description="Miele cloud API client")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="sign in with your Miele account").set_defaults(fn=cmd_login)
    sub.add_parser("devices", help="list appliances and their status").set_defaults(fn=cmd_devices)
    sub.add_parser("watch", help="stream live status updates").set_defaults(fn=cmd_watch)
    a = sub.add_parser("actions", help="show actions the appliance accepts right now")
    a.add_argument("device")
    a.set_defaults(fn=cmd_actions)
    d = sub.add_parser("do", help="send a command")
    d.add_argument("device")
    d.add_argument("command", choices=COMMANDS)
    d.set_defaults(fn=cmd_do)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
