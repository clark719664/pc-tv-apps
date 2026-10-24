"""TV brand adapters: Roku (ECP), Samsung (Tizen WS), LG (webOS WS), Vizio (SmartCast).

Every adapter exposes the same interface over a shared generic key vocabulary:
    discover()                -> [ {ip, name, model, ...} ]
    status(cfg)               -> {online, name, ...}
    press(cfg, key)           -> None (raises AdapterError on failure)
    pair(cfg, pin=None)       -> {paired: bool, save: {...}} or {pinRequired: True, save: {...}}
    needs_pairing             -> bool

Generic keys: power home back up down left right ok info menu replay search
              rev play pause fwd volup voldown mute chup chdown input exit
"""
import base64
import json
import ipaddress
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

try:
    import websocket  # websocket-client
except ImportError:
    websocket = None


class AdapterError(Exception):
    """Raised with a user-readable message when a TV command fails."""


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

WIFI_IP = None
LAN_RANGES = tuple(ipaddress.ip_network(value) for value in
                   ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def private_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
        return any(address in network for network in LAN_RANGES)
    except (ipaddress.AddressValueError, TypeError):
        return False


def set_wifi_ip(value):
    global WIFI_IP
    WIFI_IP = value if private_ipv4(value) else None


def lan_ip():
    """Use only the Wi-Fi interface address supplied by Android."""
    if not WIFI_IP:
        raise AdapterError("Connect your phone to the same Wi-Fi network as the TV")
    return WIFI_IP


def ssdp_search(st, timeout=3.0):
    """SSDP M-SEARCH, pinned to the LAN interface. Returns {ip: response_text}."""
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        f"ST: {st}\r\n"
        "MX: 2\r\n\r\n"
    ).encode()
    local = lan_ip()
    deadline = time.monotonic() + timeout
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(timeout)
    found = {}
    try:
        s.bind((local, 0))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        for _ in range(2):          # M-SEARCH is UDP; a lost packet means a missing TV
            s.sendto(msg, ("239.255.255.250", 1900))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            s.settimeout(remaining)
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                break
            if private_ipv4(addr[0]):
                found.setdefault(addr[0], data.decode(errors="replace"))
    except OSError:
        # A blocked multicast route must not prevent the bounded fallback sweep.
        pass
    finally:
        s.close()
    return found


def sweep_port(port, timeout=0.5):
    """Bounded fallback: probe the Wi-Fi address's /24 only."""
    lip = lan_ip()
    base = lip.rsplit(".", 1)[0]
    if not base or base == "0.0.0":
        return []
    bases = [base]
    hits = []
    lock = threading.Lock()

    def check(ip):
        try:
            sock = socket.create_connection((ip, port), timeout)
            sock.close()
        except OSError:
            return
        with lock:
            hits.append(ip)

    # Keep discovery resource use bounded on phones.
    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(check, (f"{b}.{n}" for b in bases for n in range(1, 255))))
    return hits


def wake_on_lan(mac):
    if not mac:
        return
    try:
        mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    except ValueError:
        return
    packet = b"\xff" * 6 + mac_bytes * 16
    local = lan_ip()
    targets = {"255.255.255.255"}
    if private_ipv4(local):
        base = local.rsplit(".", 1)[0]
        targets.add(f"{base}.255")
    for bcast in targets:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            if private_ipv4(local):
                try:
                    s.bind((local, 0))
                except OSError:
                    pass
            for port in (7, 9):
                s.sendto(packet, (bcast, port))
        except OSError:
            pass
        finally:
            s.close()


def tcp_alive(ip, port, timeout=1.5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _validated_url(url, expected_host=None):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme not in ('http', 'https', 'ws', 'wss') or
            not private_ipv4(parsed.hostname) or parsed.username or parsed.password or
            parsed.port not in (8060, 8001, 8002, 3000, 3001, 7345, 9000) or
            (expected_host is not None and parsed.hostname != expected_host)):
        raise ValueError('TV returned an unsupported local endpoint')
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('TV unexpectedly redirected the request')


def _urlopen(request, timeout=3, context=None):
    _validated_url(request.full_url if isinstance(request, urllib.request.Request) else request)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(),
                                        urllib.request.HTTPSHandler(context=context))
    return opener.open(request, timeout=timeout)


def _ws_connect(url, *args, **kwargs):
    _validated_url(url)
    kwargs['redirect_limit'] = 0
    kwargs['http_no_proxy'] = ['*']
    return websocket.create_connection(url, *args, **kwargs)


def http_json(url, timeout=3.0, method="GET", body=None, headers=None, insecure=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with _urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode())


def _require_ws():
    if websocket is None:
        raise AdapterError("websocket-client not installed (pip install websocket-client)")


def _threaded_probe(ips, probe_fn):
    """Run probe_fn(ip) across ips concurrently; return non-None results."""
    results, lock = [], threading.Lock()

    def worker(ip):
        try:
            r = probe_fn(ip)
            if r:
                with lock:
                    results.append(r)
        except Exception:
            pass

    threads = [threading.Thread(target=worker, args=(ip,), daemon=True) for ip in ips]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=4)
    return results


# --------------------------------------------------------------------------
# Roku — ECP over plain HTTP :8060
# --------------------------------------------------------------------------

ROKU_KEYS = {
    "power": "Power", "home": "Home", "back": "Back",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right", "ok": "Select",
    "info": "Info", "replay": "InstantReplay", "search": "Search",
    "rev": "Rev", "play": "Play", "pause": "Play", "fwd": "Fwd",
    "volup": "VolumeUp", "voldown": "VolumeDown", "mute": "VolumeMute",
    "chup": "ChannelUp", "chdown": "ChannelDown",
}


class Roku:
    needs_pairing = False

    @staticmethod
    def _url(cfg, path):
        return f"http://{cfg['ip']}:8060/{path}"

    @staticmethod
    def request(cfg, path, method="GET", timeout=4.0):
        req = urllib.request.Request(Roku._url(cfg, path), method=method)
        try:
            with _urlopen(req, timeout=timeout) as resp:
                return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise AdapterError(
                    "That TV is blocking the network remote (ECP Limited). "
                    "On the TV: Settings → System → Advanced system settings → "
                    "Control by mobile apps → Network access → Permissive"
                ) from e
            raise AdapterError(f"TV returned HTTP {e.code}") from e
        except OSError as e:
            raise AdapterError(f"TV not reachable ({e})") from e

    @staticmethod
    def device_info(ip, timeout=3.0):
        with _urlopen(f"http://{ip}:8060/query/device-info", timeout=timeout) as resp:
            root = ET.fromstring(resp.read())

        def f(tag):
            el = root.find(tag)
            return el.text if el is not None and el.text else ""

        return {
            "ip": ip,
            "name": f("user-device-name") or f("friendly-device-name") or f("model-name"),
            "location": f("user-device-location"),
            "model": f("model-name"),
            "mac": f("wifi-mac") or f("ethernet-mac"),
            "serial": f("serial-number"),
            "power": f("power-mode"),
        }

    @staticmethod
    def discover():
        ips = set(ssdp_search("roku:ecp"))
        ips.update(sweep_port(8060))          # multicast is unreliable on this LAN
        return _threaded_probe(ips, Roku.device_info)

    @staticmethod
    def inputs(cfg):
        """Return only safe TV-input identifiers reported by this Roku."""
        try:
            data, _ = Roku.request(cfg, "query/apps")
            root = ET.fromstring(data)
            if root.tag != "apps":
                raise ValueError("Unexpected apps response")
        except (AdapterError, ET.ParseError, ValueError) as exc:
            raise ValueError("Could not read Roku TV inputs. Wake the TV and check network access for mobile apps.") from exc
        inputs, seen = [], set()
        for app in root.findall("app"):
            input_id = app.get("id", "")
            if not re.fullmatch(r"tvinput\.[A-Za-z0-9_-]{1,64}", input_id) or input_id in seen:
                continue
            seen.add(input_id)
            inputs.append({"id": input_id, "name": (app.text or input_id).strip()[:100] or input_id})
        if not inputs:
            raise ValueError("This Roku has no configured TV inputs. Roku sticks and streaming players cannot switch the TV's inputs; on a Roku TV, set up inputs in Settings > TV inputs.")
        return inputs

    @staticmethod
    def select_input(cfg, input_id):
        if not isinstance(input_id, str) or not re.fullmatch(r"tvinput\.[A-Za-z0-9_-]{1,64}", input_id):
            raise ValueError("Choose a TV input from the input picker")
        # Requery so a stale picker cannot launch an arbitrary app or removed input.
        if input_id not in {item["id"] for item in Roku.inputs(cfg)}:
            raise ValueError("That TV input is no longer available. Open the input picker again.")
        Roku.request(cfg, "launch/" + urllib.parse.quote(input_id, safe=""), method="POST")

    @staticmethod
    def press(cfg, key):
        if key.startswith("lit:"):
            ch = key[4:]
            if len(ch) != 1:
                raise AdapterError("bad literal")
            Roku.request(cfg, f"keypress/Lit_{urllib.parse.quote(ch, safe='')}", method="POST")
            return
        if key == "backspace":
            Roku.request(cfg, "keypress/Backspace", method="POST")
            return
        if key == "enter":
            Roku.request(cfg, "keypress/Enter", method="POST")
            return
        ecp = ROKU_KEYS.get(key)
        if not ecp:
            raise AdapterError(f"Roku doesn't support '{key}'")
        Roku.request(cfg, f"keypress/{ecp}", method="POST")

    @staticmethod
    def power(cfg):
        try:
            Roku.request(cfg, "keypress/Power", method="POST", timeout=3.0)
            return "power"
        except AdapterError:
            if cfg.get("mac"):
                wake_on_lan(cfg["mac"])
                return "wake"
            raise

    @staticmethod
    def status(cfg):
        info = Roku.device_info(cfg["ip"])
        out = {"online": True, "name": info["name"], "power": info["power"]}
        try:
            data, _ = Roku.request(cfg, "query/active-app", timeout=3.0)
            app = ET.fromstring(data).find("app")
            if app is not None:
                out["activeApp"] = {"id": app.get("id") or "", "name": app.text or ""}
        except Exception:
            pass
        try:
            data, _ = Roku.request(cfg, "query/media-player", timeout=3.0)
            root = ET.fromstring(data)

            def ms(tag):
                el = root.find(tag)
                if el is None or not el.text:
                    return None
                try:
                    return int(el.text.strip().split()[0])
                except ValueError:
                    return None

            live = root.find("is_live")
            out["media"] = {
                "state": root.get("state") or "",
                "position": ms("position"),
                "duration": ms("duration"),
                "live": live is not None and (live.text or "").strip() == "true",
            }
        except Exception:
            pass
        return out

    @staticmethod
    def pair(cfg, pin=None):
        return {"paired": True, "save": {}}


# --------------------------------------------------------------------------
# Samsung — Tizen websocket :8002 (token pairing via on-TV Allow prompt)
# --------------------------------------------------------------------------

SAMSUNG_KEYS = {
    "power": "KEY_POWER", "home": "KEY_HOME", "back": "KEY_RETURN",
    "up": "KEY_UP", "down": "KEY_DOWN", "left": "KEY_LEFT", "right": "KEY_RIGHT",
    "ok": "KEY_ENTER", "info": "KEY_INFO", "menu": "KEY_MENU",
    "rev": "KEY_REWIND", "play": "KEY_PLAY", "pause": "KEY_PAUSE", "fwd": "KEY_FF",
    "volup": "KEY_VOLUP", "voldown": "KEY_VOLDOWN", "mute": "KEY_MUTE",
    "chup": "KEY_CHUP", "chdown": "KEY_CHDOWN", "input": "KEY_SOURCE", "exit": "KEY_EXIT",
}

_samsung_conns = {}
_samsung_lock = threading.Lock()


class Samsung:
    needs_pairing = True
    APP_NAME = base64.b64encode(b"PC TV Remote").decode()

    @staticmethod
    def rest_info(ip, timeout=2.5):
        j = http_json(f"http://{ip}:8001/api/v2/", timeout=timeout)
        dev = j.get("device", {})
        return {
            "ip": ip,
            "name": dev.get("name") or "Samsung TV",
            "model": dev.get("modelName", ""),
            "mac": dev.get("wifiMac", ""),
            "power": dev.get("PowerState", ""),
            "tokenAuth": dev.get("TokenAuthSupport", ""),
        }

    @staticmethod
    def discover():
        ips = set(ssdp_search("ssdp:all"))
        ips.update(ssdp_search("urn:samsung.com:device:RemoteControlReceiver:1"))
        ips.update(sweep_port(8001))
        return _threaded_probe(ips, Samsung.rest_info)

    @staticmethod
    def _connect(cfg, timeout):
        _require_ws()
        token = cfg.get("token", "")
        q = f"name={Samsung.APP_NAME}"
        if token:
            q += f"&token={token}"
        url = f"wss://{cfg['ip']}:8002/api/v2/channels/samsung.remote.control?{q}"
        conn = _ws_connect(
            url, timeout, sslopt={"cert_reqs": ssl.CERT_NONE})
        # First message: ms.channel.connect (may take until the user hits Allow)
        resp = json.loads(conn.recv())
        event = resp.get("event", "")
        if event == "ms.channel.unauthorized":
            conn.close()
            raise AdapterError("The TV denied the connection — select Allow on the TV and pair again")
        if event != "ms.channel.connect":
            conn.close()
            raise AdapterError(f"Unexpected TV response: {event or resp}")
        new_token = resp.get("data", {}).get("token")
        return conn, new_token

    @staticmethod
    def _get_conn(cfg):
        with _samsung_lock:
            conn = _samsung_conns.get(cfg["ip"])
            if conn is not None and conn.connected:
                return conn
            conn, new_token = Samsung._connect(cfg, timeout=6)
            _samsung_conns[cfg["ip"]] = conn
            return conn

    @staticmethod
    def _send(cfg, payload):
        try:
            conn = Samsung._get_conn(cfg)
            conn.send(json.dumps(payload))
        except (OSError, websocket.WebSocketException) as e:
            with _samsung_lock:
                _samsung_conns.pop(cfg["ip"], None)
            raise AdapterError(f"TV not reachable ({e})") from e

    @staticmethod
    def press(cfg, key):
        if not cfg.get("token"):
            raise AdapterError("Not paired yet — open Devices and pair with the TV")
        if key.startswith("lit:"):
            Samsung.send_text(cfg, key[4:])
            return
        code = SAMSUNG_KEYS.get(key)
        if not code:
            raise AdapterError(f"Samsung doesn't support '{key}'")
        Samsung._send(cfg, {
            "method": "ms.remote.control",
            "params": {"Cmd": "Click", "DataOfCmd": code,
                       "Option": "false", "TypeOfRemote": "SendRemoteKey"},
        })

    @staticmethod
    def send_text(cfg, text):
        Samsung._send(cfg, {
            "method": "ms.remote.control",
            "params": {"Cmd": base64.b64encode(text.encode()).decode(),
                       "DataOfCmd": "base64", "TypeOfRemote": "SendInputString"},
        })

    @staticmethod
    def power(cfg):
        try:
            Samsung.press(cfg, "power")
            return "power"
        except AdapterError:
            if cfg.get("mac"):
                wake_on_lan(cfg["mac"])
                return "wake"
            raise

    @staticmethod
    def status(cfg):
        try:
            info = Samsung.rest_info(cfg["ip"])
            return {"online": True, "name": info["name"] or cfg.get("name", "Samsung TV"),
                    "power": info["power"], "paired": bool(cfg.get("token"))}
        except OSError:
            return {"online": False, "name": cfg.get("name", "Samsung TV"),
                    "paired": bool(cfg.get("token"))}

    @staticmethod
    def pair(cfg, pin=None):
        """Connect fresh; the TV pops an Allow prompt. Blocks until user answers."""
        with _samsung_lock:
            old = _samsung_conns.pop(cfg["ip"], None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
        conn, token = Samsung._connect({**cfg, "token": cfg.get("token", "")}, timeout=45)
        with _samsung_lock:
            _samsung_conns[cfg["ip"]] = conn
        save = {}
        if token:
            save["token"] = token
        try:
            save["mac"] = Samsung.rest_info(cfg["ip"]).get("mac", "")
        except Exception:
            pass
        if not token and not cfg.get("token"):
            raise AdapterError("TV connected but sent no token — on the TV allow the "
                               "connection, and check Settings > General > External Device "
                               "Manager > Device Connection Manager")
        return {"paired": True, "save": save}


# --------------------------------------------------------------------------
# LG — webOS websocket :3001/:3000 (client-key pairing via on-TV prompt)
# --------------------------------------------------------------------------

LG_SIGNATURE = (
    "eyJhbGdvcml0aG0iOiJSU0EtU0hBMjU2Iiwia2V5SWQiOiJ0ZXN0LXNpZ25pbm"
    "ctY2VydCIsInNpZ25hdHVyZVZlcnNpb24iOjF9.hrVRgjCwXVvE2OOSpDZ58hR"
    "+59aFNwYDyjQgKk3auukd7pcegmE2CzPCa0bJ0ZsRAcKkCTJrWo5iDzNhMBWRy"
    "aMOv5zWSrthlf7G128qvIlpMT0YNY+n/FaOHE73uLrS/g7swl3/qH/BGFG2Hu4"
    "RlL48eb3lLKqTt2xKHdCs6Cd4RMfJPYnzgvI4BNrFUKsjkcu+WD4OO2A27Pq1n"
    "50cMchmcaXadJhGrOqH5YmHdOCj5NSHzJYrsW0HPlpuAx/ECMeIZYDh6RMqaFM"
    "2DXzdKX9NmmyqzJ3o/0lkk/N97gfVRLW5hA29yeAwaCViZNCP8iC9aO0q9fQoj"
    "oa7NQnAtw=="
)

LG_REGISTER_PAYLOAD = {
    "forcePairing": False,
    "pairingType": "PROMPT",
    "manifest": {
        "appVersion": "1.1",
        "manifestVersion": 1,
        "permissions": [
            "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP", "CLOSE", "TEST_OPEN",
            "TEST_PROTECTED", "CONTROL_AUDIO", "CONTROL_DISPLAY",
            "CONTROL_INPUT_JOYSTICK", "CONTROL_INPUT_MEDIA_RECORDING",
            "CONTROL_INPUT_MEDIA_PLAYBACK", "CONTROL_INPUT_TV", "CONTROL_POWER",
            "READ_APP_STATUS", "READ_CURRENT_CHANNEL", "READ_INPUT_DEVICE_LIST",
            "READ_NETWORK_STATE", "READ_RUNNING_APPS", "READ_TV_CHANNEL_LIST",
            "WRITE_NOTIFICATION_TOAST", "READ_POWER_STATE", "READ_COUNTRY_INFO",
            "READ_SETTINGS", "CONTROL_TV_SCREEN", "CONTROL_TV_STANBY",
            "CONTROL_FAVORITE_GROUP", "CONTROL_USER_INFO", "CHECK_BLUETOOTH_DEVICE",
            "CONTROL_BLUETOOTH", "CONTROL_TIMER_INFO", "STB_INTERNAL_CONNECTION",
            "CONTROL_RECORDING", "READ_RECORDING_STATE", "WRITE_RECORDING_LIST",
            "READ_RECORDING_LIST", "READ_RECORDING_SCHEDULE",
            "WRITE_RECORDING_SCHEDULE", "READ_STORAGE_DEVICE_LIST",
            "READ_TV_PROGRAM_INFO", "CONTROL_BOX_CHANNEL", "READ_TV_ACR_AUTH_TOKEN",
            "READ_TV_CONTENT_STATE", "READ_TV_CURRENT_TIME", "ADD_LAUNCHER_CHANNEL",
            "SET_CHANNEL_SKIP", "RELEASE_CHANNEL_SKIP", "CONTROL_CHANNEL_BLOCK",
            "DELETE_SELECT_CHANNEL", "CONTROL_CHANNEL_GROUP", "SCAN_TV_CHANNELS",
            "CONTROL_TV_POWER", "CONTROL_WOL",
        ],
        "signatures": [{"signature": LG_SIGNATURE, "signatureVersion": 1}],
        "signed": {
            "appId": "com.lge.test",
            "created": "20140509",
            "localizedAppNames": {"": "LG Remote App"},
            "localizedVendorNames": {"": "LG Electronics"},
            "permissions": [
                "TEST_SECURE", "CONTROL_INPUT_TEXT", "CONTROL_MOUSE_AND_KEYBOARD",
                "READ_INSTALLED_APPS", "READ_LGE_SDX", "READ_NOTIFICATIONS",
                "SEARCH", "WRITE_SETTINGS", "WRITE_NOTIFICATION_ALERT",
                "CONTROL_POWER", "READ_CURRENT_CHANNEL", "READ_RUNNING_APPS",
                "READ_UPDATE_INFO", "UPDATE_FROM_REMOTE_APP",
                "READ_LGE_TV_INPUT_EVENTS", "READ_TV_CURRENT_TIME",
            ],
            "serial": "2f930e2d2cfe083771f68e4fe7bb07",
            "vendorId": "com.lge",
        },
    },
}

LG_BUTTONS = {
    "home": "HOME", "back": "BACK", "up": "UP", "down": "DOWN", "left": "LEFT",
    "right": "RIGHT", "ok": "ENTER", "info": "INFO", "menu": "MENU",
    "rev": "REWIND", "play": "PLAY", "pause": "PAUSE", "fwd": "FASTFORWARD",
    "volup": "VOLUMEUP", "voldown": "VOLUMEDOWN", "mute": "MUTE",
    "chup": "CHANNELUP", "chdown": "CHANNELDOWN", "exit": "EXIT",
}

_lg_conns = {}   # ip -> {"main": ws, "input": ws}
_lg_lock = threading.Lock()
_lg_msg_id = [0]


class LG:
    needs_pairing = True

    @staticmethod
    def _ssdp_webos(text):
        service = "urn:lge-com:service:webos-second-screen:1"
        for line in text.splitlines():
            name, _, value = line.partition(":")
            name, value = name.strip().lower(), value.strip().lower()
            if name == "st" and value == service:
                return True
            if name == "usn" and value.rsplit("::", 1)[-1] == service:
                return True
            if name == "server" and any(token.startswith("webos/") for token in value.split()):
                return True
        return False

    @staticmethod
    def _webos_hello(ip):
        """Read identity before registration; never initiate pairing."""
        if websocket is None:
            return False
        conn = None
        try:
            conn = LG._open_ws(ip, timeout=1.0)
            conn.send(json.dumps({"id": "discovery", "type": "hello", "payload": {
                "sdkVersion": "1.0", "appId": "pc-tv-remote", "appName": "PC TV Remote"}}))
            reply = json.loads(conn.recv())
            if not isinstance(reply, dict) or reply.get("type") != "hello":
                return False
            payload = reply.get("payload")
            return (isinstance(payload, dict)
                    and str(payload.get("deviceType", "")).lower() == "tv"
                    and str(payload.get("deviceOS", "")).lower() == "webos"
                    and isinstance(payload.get("deviceUUID"), str)
                    and bool(payload["deviceUUID"].strip()))
        except (OSError, ValueError, TypeError, websocket.WebSocketException):
            return False
        finally:
            if conn is not None:
                try:
                    conn.close(timeout=0.2)
                except (OSError, websocket.WebSocketException):
                    pass

    @staticmethod
    def discover():
        found = {}
        try:
            replies = ssdp_search("urn:lge-com:service:webos-second-screen:1")
            found.update({ip: text for ip, text in replies.items() if LG._ssdp_webos(text)})
        except OSError:
            pass
        try:
            for ip in sweep_port(3001):
                found.setdefault(ip, "")
        except OSError:
            pass
        # Some firmwares only answer generic searches, even when others have
        # already answered the service-specific search or port sweep.
        try:
            allfound = ssdp_search("ssdp:all")
            for ip, text in allfound.items():
                if LG._ssdp_webos(text):
                    found[ip] = text
        except OSError:
            pass
        return [{"ip": ip, "name": "LG webOS TV", "model": "webOS"}
                for ip, text in found.items() if text or LG._webos_hello(ip)]

    @staticmethod
    def _open_ws(ip, timeout):
        _require_ws()
        try:
            return _ws_connect(
                f"wss://{ip}:3001/", timeout, sslopt={"cert_reqs": ssl.CERT_NONE})
        except (OSError, websocket.WebSocketException):
            return _ws_connect(f"ws://{ip}:3000/", timeout)

    @staticmethod
    def _next_id():
        _lg_msg_id[0] += 1
        return f"pcrem_{_lg_msg_id[0]}"

    @staticmethod
    def _register(conn, cfg, timeout):
        payload = dict(LG_REGISTER_PAYLOAD)
        if cfg.get("key"):
            payload["client-key"] = cfg["key"]
        conn.send(json.dumps({"type": "register", "id": LG._next_id(), "payload": payload}))
        conn.sock.settimeout(timeout)
        while True:
            msg = json.loads(conn.recv())
            if msg.get("type") == "registered":
                return msg["payload"].get("client-key")
            if msg.get("type") == "error":
                raise AdapterError(f"TV refused pairing: {msg.get('error', 'unknown error')}")
            # else: PROMPT notice — keep waiting for the user to hit Allow

    @staticmethod
    def _request(conn, uri, payload=None, timeout=5):
        mid = LG._next_id()
        obj = {"type": "request", "id": mid, "uri": uri}
        if payload is not None:
            obj["payload"] = payload
        conn.send(json.dumps(obj))
        conn.sock.settimeout(timeout)
        while True:
            msg = json.loads(conn.recv())
            if msg.get("id") == mid:
                return msg.get("payload", {})

    @staticmethod
    def _get_conns(cfg, pair_timeout=8):
        ip = cfg["ip"]
        with _lg_lock:
            entry = _lg_conns.get(ip)
            if entry and entry["main"].connected and entry["input"] and entry["input"].connected:
                return entry
            try:
                main = LG._open_ws(ip, timeout=6)
            except (OSError, websocket.WebSocketException) as e:
                raise AdapterError(f"TV not reachable ({e})") from e
            key = LG._register(main, cfg, timeout=pair_timeout)
            if key and key != cfg.get("key"):
                cfg["key"] = key  # caller persists via pair()
            sock_info = LG._request(
                main, "ssap://com.webos.service.networkinput/getPointerInputSocket")
            input_ws = None
            path = sock_info.get("socketPath")
            if path:
                _validated_url(path, expected_host=ip)
                input_ws = _ws_connect(
                    path, 6, sslopt={"cert_reqs": ssl.CERT_NONE})
            entry = {"main": main, "input": input_ws}
            _lg_conns[ip] = entry
            return entry

    @staticmethod
    def _drop(ip):
        with _lg_lock:
            entry = _lg_conns.pop(ip, None)
        if entry:
            for c in entry.values():
                try:
                    if c:
                        c.close()
                except Exception:
                    pass

    @staticmethod
    def press(cfg, key):
        if not cfg.get("key"):
            raise AdapterError("Not paired yet — open Devices and pair with the TV")
        if key == "power":
            LG.power(cfg)
            return
        name = LG_BUTTONS.get(key)
        if not name:
            raise AdapterError(f"LG doesn't support '{key}'")
        try:
            conns = LG._get_conns(cfg)
            if conns["input"] is None:
                raise AdapterError("TV gave no input socket")
            conns["input"].send(f"type:button\nname:{name}\n\n")
        except (OSError, websocket.WebSocketException) as e:
            LG._drop(cfg["ip"])
            raise AdapterError(f"TV not reachable ({e})") from e

    @staticmethod
    def power(cfg):
        try:
            conns = LG._get_conns(cfg)
            LG._request(conns["main"], "ssap://system/turnOff")
            return "power"
        except (AdapterError, OSError, websocket.WebSocketException):
            LG._drop(cfg["ip"])
            if cfg.get("mac"):
                wake_on_lan(cfg["mac"])
                return "wake"
            raise

    @staticmethod
    def status(cfg):
        online = tcp_alive(cfg["ip"], 3001) or tcp_alive(cfg["ip"], 3000)
        return {"online": online, "name": cfg.get("name", "LG webOS TV"),
                "paired": bool(cfg.get("key"))}

    @staticmethod
    def pair(cfg, pin=None):
        """Register with the TV; user must hit Allow on the TV. Blocks up to 60s."""
        LG._drop(cfg["ip"])
        try:
            main = LG._open_ws(cfg["ip"], timeout=8)
        except (OSError, websocket.WebSocketException) as e:
            raise AdapterError(f"TV not reachable ({e})") from e
        key = LG._register(main, cfg, timeout=60)
        try:
            main.close()
        except Exception:
            pass
        if not key:
            raise AdapterError("TV did not return a pairing key")
        return {"paired": True, "save": {"key": key}}


# --------------------------------------------------------------------------
# Vizio — SmartCast HTTPS :7345/:9000 (PIN pairing)
# --------------------------------------------------------------------------

VIZIO_KEYS = {
    "up": (3, 8), "down": (3, 0), "left": (3, 1), "right": (3, 7), "ok": (3, 2),
    "back": (4, 0), "home": (4, 15), "menu": (4, 8), "info": (4, 6), "exit": (9, 0),
    "play": (2, 3), "pause": (2, 2), "fwd": (2, 0), "rev": (2, 1),
    "volup": (5, 1), "voldown": (5, 0), "mute": (5, 4),
    "chup": (8, 1), "chdown": (8, 0), "input": (7, 1),
    "power": (11, 2),
}

VIZIO_DEVICE_ID = "pc-tv-remote-0001"


class Vizio:
    needs_pairing = True
    PORTS = (7345, 9000)

    @staticmethod
    def _base(cfg):
        port = cfg.get("port") or 7345
        return f"https://{cfg['ip']}:{port}"

    @staticmethod
    def _call(cfg, path, method="GET", body=None, timeout=5.0):
        headers = {}
        if cfg.get("token"):
            headers["AUTH"] = cfg["token"]
        try:
            return http_json(f"{Vizio._base(cfg)}{path}", timeout=timeout,
                             method=method, body=body, headers=headers, insecure=True)
        except OSError as e:
            raise AdapterError(f"TV not reachable ({e})") from e

    @staticmethod
    def detect_port(ip):
        for port in Vizio.PORTS:
            if tcp_alive(ip, port, timeout=1.0):
                return port
        return None

    @staticmethod
    def discover():
        devices = []
        candidates = set(ssdp_search("ssdp:all"))
        candidates.update(sweep_port(7345))
        candidates.update(sweep_port(9000))
        for ip in candidates:
            port = Vizio.detect_port(ip)
            if port:
                devices.append({"ip": ip, "port": port, "name": "Vizio SmartCast TV",
                                "model": "SmartCast"})
        return devices

    @staticmethod
    def pair(cfg, pin=None):
        if not cfg.get("port"):
            port = Vizio.detect_port(cfg["ip"])
            if not port:
                raise AdapterError("No SmartCast service found on that IP (ports 7345/9000)")
            cfg["port"] = port
        if pin is None:
            # step 1: ask the TV to show a PIN
            j = Vizio._call(cfg, "/pairing/start", method="PUT", body={
                "DEVICE_ID": VIZIO_DEVICE_ID, "DEVICE_NAME": "PC TV Remote"})
            item = j.get("ITEM", {})
            token = item.get("PAIRING_REQ_TOKEN")
            if token is None:
                raise AdapterError(f"Pairing refused: {j.get('STATUS', {}).get('DETAIL', j)}")
            return {"pinRequired": True,
                    "save": {"port": cfg["port"], "pairToken": token,
                             "challenge": item.get("CHALLENGE_TYPE", 1)}}
        # step 2: user typed the PIN from the TV screen
        j = Vizio._call(cfg, "/pairing/pair", method="PUT", body={
            "DEVICE_ID": VIZIO_DEVICE_ID,
            "CHALLENGE_TYPE": cfg.get("challenge", 1),
            "RESPONSE_VALUE": str(pin).strip(),
            "PAIRING_REQ_TOKEN": cfg.get("pairToken"),
        })
        auth = j.get("ITEM", {}).get("AUTH_TOKEN")
        if not auth:
            raise AdapterError(f"Wrong PIN or pairing expired: {j.get('STATUS', {}).get('DETAIL', j)}")
        return {"paired": True, "save": {"token": auth, "pairToken": None, "challenge": None}}

    @staticmethod
    def press(cfg, key):
        if not cfg.get("token"):
            raise AdapterError("Not paired yet — open Devices and pair with the TV")
        code = VIZIO_KEYS.get(key)
        if not code:
            raise AdapterError(f"Vizio doesn't support '{key}'")
        j = Vizio._call(cfg, "/key_command/", method="PUT", body={
            "KEYLIST": [{"CODESET": code[0], "CODE": code[1], "ACTION": "KEYPRESS"}]})
        result = j.get("STATUS", {}).get("RESULT", "")
        if result not in ("SUCCESS", ""):
            raise AdapterError(f"TV rejected the key: {j['STATUS'].get('DETAIL', result)}")

    @staticmethod
    def power(cfg):
        Vizio.press(cfg, "power")
        return "power"

    @staticmethod
    def status(cfg):
        port = cfg.get("port") or 7345
        return {"online": tcp_alive(cfg["ip"], port), "name": cfg.get("name", "Vizio SmartCast TV"),
                "paired": bool(cfg.get("token"))}


# --------------------------------------------------------------------------
# Google TV / Android TV — remote protocol v2 :6466 (cert pairing, code on TV)
# --------------------------------------------------------------------------

GOOGLETV_KEYS = {
    "power": "POWER", "home": "HOME", "back": "BACK",
    "up": "DPAD_UP", "down": "DPAD_DOWN", "left": "DPAD_LEFT", "right": "DPAD_RIGHT",
    "ok": "DPAD_CENTER", "info": "INFO", "menu": "MENU", "search": "SEARCH",
    "rev": "MEDIA_REWIND", "play": "MEDIA_PLAY_PAUSE", "pause": "MEDIA_PLAY_PAUSE",
    "fwd": "MEDIA_FAST_FORWARD",
    "volup": "VOLUME_UP", "voldown": "VOLUME_DOWN", "mute": "VOLUME_MUTE",
    "chup": "CHANNEL_UP", "chdown": "CHANNEL_DOWN", "input": "TV_INPUT",
}

DATA_DIR = None  # set by the server at startup (where cert files live)

_gtv_loop = None
_gtv_loop_lock = threading.Lock()
_gtv_remotes = {}    # ip -> connected AndroidTVRemote
_gtv_pairing = {}    # ip -> AndroidTVRemote mid-pairing


def _gtv_run(coro, timeout=25):
    """Run a coroutine on the shared background asyncio loop."""
    global _gtv_loop
    import asyncio
    with _gtv_loop_lock:
        if _gtv_loop is None:
            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, daemon=True).start()
            _gtv_loop = loop
    fut = asyncio.run_coroutine_threadsafe(coro, _gtv_loop)
    return fut.result(timeout)


def _gtv_call(callback, *args):
    """Run transport mutations on the event loop which owns the connection."""
    async def invoke():
        return callback(*args)
    return _gtv_run(invoke())


def _gtv_certs():
    import os
    base = DATA_DIR or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "googletv_cert.pem"), os.path.join(base, "googletv_key.pem")


def _gtv_new(ip):
    from androidtvremote2 import AndroidTVRemote
    cert, key = _gtv_certs()
    return AndroidTVRemote("PC TV Remote", cert, key, ip, loop=_gtv_loop)


def _local_subnet():
    ip = lan_ip()
    if not private_ipv4(ip):
        return None
    return ip.rsplit(".", 1)[0]


class GoogleTV:
    needs_pairing = True

    @staticmethod
    def discover():
        """No SSDP: sweep the local /24 for the remote-protocol port 6466."""
        prefix = _local_subnet()
        if not prefix:
            return []
        candidates = [f"{prefix}.{i}" for i in range(1, 255)]
        return _threaded_probe(
            candidates,
            lambda ip: {"ip": ip, "name": "Google TV / Android TV", "model": "Android TV"}
            if tcp_alive(ip, 6466, timeout=0.7) else None,
        )

    @staticmethod
    def _errmsg(e):
        name = type(e).__name__
        if "InvalidAuth" in name:
            return "Pairing rejected — pair again and enter the code shown on the TV"
        if "CannotConnect" in name:
            return "TV not reachable — is it on and on the same network?"
        return f"{name}: {e}"

    @staticmethod
    def _get_remote(cfg):
        ip = cfg["ip"]
        remote = _gtv_remotes.get(ip)
        if remote is not None:
            return remote

        async def connect():
            r = _gtv_new(ip)
            await r.async_generate_cert_if_missing()
            await r.async_connect()
            r.keep_reconnecting()
            return r

        try:
            remote = _gtv_run(connect())
        except Exception as e:
            raise AdapterError(GoogleTV._errmsg(e)) from e
        _gtv_remotes[ip] = remote
        return remote

    @staticmethod
    def press(cfg, key):
        if not cfg.get("paired"):
            raise AdapterError("Not paired yet — open Devices and pair with the TV")
        if key.startswith("lit:"):
            GoogleTV.send_text(cfg, key[4:])
            return
        code = GOOGLETV_KEYS.get(key)
        if not code:
            raise AdapterError(f"Google TV doesn't support '{key}'")
        remote = GoogleTV._get_remote(cfg)
        try:
            _gtv_call(remote.send_key_command, code)
        except Exception as e:
            _gtv_remotes.pop(cfg["ip"], None)
            raise AdapterError(GoogleTV._errmsg(e)) from e

    @staticmethod
    def send_text(cfg, text):
        remote = GoogleTV._get_remote(cfg)
        try:
            _gtv_call(remote.send_text, text)
        except Exception as e:
            raise AdapterError(GoogleTV._errmsg(e)) from e

    @staticmethod
    def power(cfg):
        GoogleTV.press(cfg, "power")
        return "power"

    @staticmethod
    def status(cfg):
        ip = cfg["ip"]
        out = {"online": tcp_alive(ip, 6466), "name": cfg.get("name", "Google TV"),
               "paired": bool(cfg.get("paired"))}
        remote = _gtv_remotes.get(ip)
        if remote is not None:
            try:
                app = remote.current_app
                if app:
                    out["activeApp"] = {"id": app, "name": app.rsplit(".", 2)[-1].title()}
                out["power"] = "PowerOn" if remote.is_on else "Standby"
            except Exception:
                pass
        return out

    @staticmethod
    def pair(cfg, pin=None):
        ip = cfg["ip"]
        if pin is None:
            async def start():
                r = _gtv_new(ip)
                await r.async_generate_cert_if_missing()
                await r.async_start_pairing()
                return r

            old = _gtv_pairing.pop(ip, None)
            if old is not None:
                try:
                    _gtv_call(old.disconnect)
                except Exception:
                    pass
            try:
                _gtv_pairing[ip] = _gtv_run(start())
            except Exception as e:
                raise AdapterError(GoogleTV._errmsg(e)) from e
            # name lookup is a nice-to-have
            name = "Google TV"
            try:
                info = _gtv_run(_gtv_pairing[ip].async_get_name_and_mac(), timeout=6)
                if info and info[0]:
                    name = info[0]
            except Exception:
                pass
            return {"pinRequired": True, "save": {"name": name}}

        remote = _gtv_pairing.pop(ip, None)
        if remote is None:
            raise AdapterError("Pairing session expired — start pairing again")
        try:
            _gtv_run(remote.async_finish_pairing(str(pin).strip()))
        except Exception as e:
            raise AdapterError(GoogleTV._errmsg(e)) from e
        try:
            _gtv_call(remote.disconnect)
        except Exception:
            pass
        return {"paired": True, "save": {"paired": True}}


ADAPTERS = {"roku": Roku, "samsung": Samsung, "lg": LG, "vizio": Vizio, "googletv": GoogleTV}
