"""Native-only JSON interface. Configuration and credentials never leave app storage."""
import json
import os
from pathlib import Path
import re
import threading
import uuid

import adapters

_lock = threading.RLock()
KEYS = frozenset('power home back up down left right ok info menu replay search rev play pause fwd volup voldown mute chup chdown input exit backspace enter'.split())
PUBLIC_FIELDS = ('id', 'brand', 'ip', 'name', 'model', 'paired')
SAVE_FIELDS = frozenset(('token', 'key', 'mac', 'port', 'pairToken', 'challenge', 'paired', 'name'))


def _public(device):
    return {key: device[key] for key in PUBLIC_FIELDS if key in device}


def _brand(value):
    if not isinstance(value, str) or value not in adapters.ADAPTERS:
        raise ValueError('Choose a supported TV brand')
    return value


def _ip(value):
    if not isinstance(value, str) or not adapters.private_ipv4(value):
        raise ValueError('Enter a private Wi-Fi IPv4 address, such as 192.168.1.20')
    return value


def _load(path):
    if not path.exists():
        return []
    try:
        records = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(records, list):
            raise ValueError()
        for record in records:
            _brand(record['brand'])
            _ip(record['ip'])
        return records
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError('Saved TV settings could not be read. Clear app storage to reset.') from exc


def _save(path, records):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(records, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _close(ip):
    adapters.LG._drop(ip)
    connection = adapters._samsung_conns.pop(ip, None)
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass
    for cache in (adapters._gtv_remotes, adapters._gtv_pairing):
        remote = cache.pop(ip, None)
        if remote is not None:
            try:
                adapters._gtv_call(remote.disconnect)
            except Exception:
                pass


def call(operation, payload_json, data_dir, wifi_ip):
    """Called on Java's serial executor; returns a JSON envelope without secrets."""
    with _lock:
        try:
            payload = json.loads(payload_json)
            if not isinstance(payload, dict):
                raise ValueError('Invalid request')
            directory = Path(data_dir)
            directory.mkdir(parents=True, exist_ok=True)
            adapters.DATA_DIR = str(directory)
            adapters.set_wifi_ip(wifi_ip)
            path = directory / 'remote-devices.json'
            devices = _load(path)
            if operation == 'list':
                return json.dumps({'ok': True, 'devices': [_public(d) for d in devices]})
            if operation == 'add':
                brand, ip = _brand(payload.get('brand')), _ip(payload.get('ip'))
                existing = next((d for d in devices if d['brand'] == brand and d['ip'] == ip), None)
                if existing is None:
                    existing = {'id': str(uuid.uuid4()), 'brand': brand, 'ip': ip,
                                'name': str(payload.get('name') or brand.title())[:100],
                                'paired': not adapters.ADAPTERS[brand].needs_pairing}
                    devices.append(existing)
                    _save(path, devices)
                result = {'device': _public(existing), 'devices': [_public(d) for d in devices]}
            elif operation == 'discover':
                adapters.lan_ip()
                brand = _brand(payload.get('brand'))
                found, seen, warning = [], set(), ''
                try:
                    for item in adapters.ADAPTERS[brand].discover():
                        if not isinstance(item, dict) or not adapters.private_ipv4(item.get('ip')):
                            continue
                        if item['ip'] in seen:
                            continue
                        seen.add(item['ip'])
                        found.append({'brand': brand, 'ip': item['ip'],
                                      'name': str(item.get('name') or brand.title())[:100],
                                      'model': str(item.get('model') or '')[:100]})
                except Exception:
                    warning = 'Discovery was interrupted. Results may be incomplete; you can add the TV by IP.'
                # Keep every discovered TV available for switching, not only
                # the one selected in the discovery result dialog.
                for item in found:
                    existing = next((d for d in devices if d['brand'] == brand and d['ip'] == item['ip']), None)
                    if existing is None:
                        devices.append({**item, 'id': str(uuid.uuid4()),
                                        'paired': not adapters.ADAPTERS[brand].needs_pairing})
                    else:
                        existing.update(name=item['name'], model=item['model'])
                if found:
                    _save(path, devices)
                result = {'devices': found, 'savedDevices': [_public(d) for d in devices], 'warning': warning}
            else:
                device = next((d for d in devices if d['id'] == payload.get('id')), None)
                if device is None:
                    raise ValueError('Select a saved TV first')
                adapter = adapters.ADAPTERS[device['brand']]
                if operation == 'forget':
                    _close(device['ip'])
                    devices.remove(device)
                    _save(path, devices)
                    result = {'devices': [_public(d) for d in devices]}
                else:
                    adapters.lan_ip()
                    if operation == 'pair':
                        pin = payload.get('pin') or None
                        if pin is not None and (not isinstance(pin, str) or not re.fullmatch(r'[A-Za-z0-9]{1,16}', pin)):
                            raise ValueError('Enter the pairing code displayed on your TV')
                        response = adapter.pair(dict(device), pin)
                        updates = response.get('save', {})
                        device.update({key: value for key, value in updates.items() if key in SAVE_FIELDS})
                        if response.get('paired'):
                            device['paired'] = True
                        _save(path, devices)
                        result = {'paired': bool(response.get('paired')), 'pinRequired': bool(response.get('pinRequired')),
                                  'device': _public(device)}
                    elif operation == 'status':
                        status = adapter.status(dict(device))
                        result = {'status': {key: status[key] for key in ('online', 'name', 'power', 'paired', 'activeApp') if key in status}}
                    elif operation == 'inputs':
                        if device['brand'] != 'roku':
                            raise ValueError('This TV uses its remote Input button instead of a Roku input picker')
                        result = {'inputs': adapter.inputs(dict(device))}
                    elif operation == 'input':
                        if device['brand'] != 'roku':
                            raise ValueError('This TV uses its remote Input button instead of a Roku input picker')
                        adapter.select_input(dict(device), payload.get('input'))
                        result = {'sent': True}
                    elif operation == 'press':
                        key = payload.get('key')
                        if not isinstance(key, str) or key not in KEYS:
                            raise ValueError('Unsupported remote command')
                        if key == 'power':
                            adapter.power(dict(device))
                        else:
                            adapter.press(dict(device), key)
                        result = {'sent': True}
                    elif operation == 'text':
                        value = payload.get('text')
                        if not isinstance(value, str) or not 1 <= len(value) <= 200 or any(ord(ch) < 32 for ch in value):
                            raise ValueError('Enter 1–200 characters without control characters')
                        if device['brand'] == 'roku':
                            for character in value:
                                adapter.press(dict(device), 'lit:' + character)
                        elif device['brand'] in ('samsung', 'googletv'):
                            adapter.send_text(dict(device), value)
                        else:
                            raise ValueError('Text input is available for Roku, Samsung and Google TV')
                        result = {'sent': True}
                    else:
                        raise ValueError('Unsupported action')
            return json.dumps({'ok': True, **result}, ensure_ascii=False)
        except ValueError as exc:
            return json.dumps({'ok': False, 'error': str(exc)})
        except Exception:
            # Protocol exceptions can contain credentials or remote-provided URLs.
            return json.dumps({'ok': False, 'error': 'TV connection failed. Check Wi-Fi, wake the TV, and pair again if needed. The selected command may not be supported by this model.'})
