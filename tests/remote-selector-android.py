"""UI regression for an installed Remote APK on a disposable Android emulator.

Run with ANDROID_HOME set and one emulator connected. Adds two fake Roku IPs,
checks switching and process persistence, and removes those test entries.
Never run against a personal phone: the emulator serial is required explicitly.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

serial = sys.argv[1] if len(sys.argv) == 2 else ''
if not serial.startswith('emulator-'):
    raise SystemExit('Usage: python tests/remote-selector-android.py emulator-5554')
adb_path = Path(os.environ['ANDROID_HOME']) / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
package = 'com.in3rt1a.pctv.remote'


def adb(*args):
    return subprocess.check_output([str(adb_path), '-s', serial, *args], text=True, stderr=subprocess.STDOUT)


def nodes():
    adb('shell', 'uiautomator', 'dump', '/sdcard/selector-test.xml')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'ui.xml'
        adb('pull', '/sdcard/selector-test.xml', str(path))
        return list(ET.parse(path).iter('node'))


def tap_node(node):
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.get('bounds')))
    assert node.get('enabled') == 'true', node.attrib
    adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))


def tap(text=None, cls=None, resource=None):
    matches = [n for n in nodes() if (text is None or n.get('text', '').casefold() == text.casefold())
               and (cls is None or n.get('class') == cls)
               and (resource is None or n.get('resource-id') == resource)]
    assert len(matches) == 1, (text, cls, len(matches))
    tap_node(matches[0])


def wait(text):
    for _ in range(8):
        found = nodes()
        if any(text in n.get('text', '') for n in found):
            return found
    raise AssertionError((text, [n.get('text') for n in found if n.get('text')]))


def selector():
    matches = [n for n in nodes() if n.get('content-desc', '').startswith('Choose TV:')]
    assert len(matches) == 1
    return matches[0]


def choose(ip):
    tap_node(selector())
    found = wait('Choose TV')
    labels = [n.get('text') for n in found if n.get('class') == 'android.widget.CheckedTextView']
    assert all(any(target in label for label in labels) for target in ('10.0.2.2', '10.0.2.3')), labels
    tap('Roku · '+ip)
    assert ip in selector().get('text')


adb('shell', 'am', 'force-stop', package)
adb('shell', 'am', 'start', '-n', package+'/.MainActivity')
wait('PC TV Remote')
for ip in ('10.0.2.2', '10.0.2.3'):
    tap('TVs')
    tap('Add by IP')
    tap(cls='android.widget.EditText')
    adb('shell', 'input', 'text', ip)
    tap('Save TV')
    wait('TV saved.')
choose('10.0.2.2')
choose('10.0.2.3')
print('PASS: picker contains both TVs and switches in both directions', flush=True)
adb('shell', 'am', 'force-stop', package)
adb('shell', 'am', 'start', '-n', package+'/.MainActivity')
wait('Ready when you are.')
assert '10.0.2.3' in selector().get('text')
choose('10.0.2.2')
print('PASS: selection and full TV list survive process restart', flush=True)
tap('TVs')
tap('Check TV')
for _ in range(8):
    if selector().get('enabled') == 'true':
        break
else:
    raise AssertionError('Selector remained disabled after checking TV status')
choose('10.0.2.3')
print('PASS: selector remains usable after network status completes', flush=True)
for _ in range(2):
    tap('TVs')
    tap('Forget TV')
    tap(resource='android:id/button1')
    wait('TV forgotten.')
print('PASS: test TV entries removed', flush=True)
