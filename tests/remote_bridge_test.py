import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'android/remote/src/main/python'))
import remote_bridge as bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.adapter = Mock(needs_pairing=True)
        self.adapter.pair.return_value = {'paired': True, 'save': {'token': 'secret'}}
        self.adapter.status.return_value = {'online': True}
        self.patcher = patch.dict(bridge.adapters.ADAPTERS, {'roku': self.adapter})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def call(self, op, **payload):
        return json.loads(bridge.call(op, json.dumps(payload), self.temp.name, '192.168.1.5'))

    def add(self):
        return self.call('add', brand='roku', ip='192.168.1.20', name='Bedroom')['device']['id']

    def test_rejects_non_lan_targets_and_unknown_brand(self):
        for ip in ['127.0.0.1', '8.8.8.8', 'https://192.168.1.2', '192.168.1.2:80', '::1', '169.254.1.2', '100.64.0.2']:
            self.assertFalse(self.call('add', brand='roku', ip=ip)['ok'], ip)
        self.assertFalse(self.call('add', brand='other', ip='192.168.1.2')['ok'])

    def test_pair_persists_secret_without_returning_it(self):
        ident = self.add()
        result = self.call('pair', id=ident)
        self.assertTrue(result['paired'])
        self.assertNotIn('secret', json.dumps(result))
        self.call('press', id=ident, key='home')
        self.assertEqual(self.adapter.press.call_args.args[0]['token'], 'secret')
        self.assertNotIn('secret', json.dumps(self.call('list')))

    def test_pending_pair_state_saved_for_pin_step(self):
        ident = self.add()
        self.adapter.pair.side_effect = [
            {'pinRequired': True, 'save': {'pairToken': 'pending', 'challenge': 1}},
            {'paired': True, 'save': {'token': 'new', 'pairToken': None}},
        ]
        self.assertTrue(self.call('pair', id=ident)['pinRequired'])
        self.assertTrue(self.call('pair', id=ident, pin='1234')['paired'])
        self.assertEqual(self.adapter.pair.call_args.args[0]['pairToken'], 'pending')

    def test_unknown_command_never_reaches_adapter(self):
        ident = self.add()
        for key in ['launch/http://evil', 'lit:x', 'not-a-command']:
            self.assertFalse(self.call('press', id=ident, key=key)['ok'])
        self.adapter.press.assert_not_called()

    def test_partial_discovery_retains_good_devices(self):
        def discovery():
            yield {'ip': '192.168.1.20', 'name': 'Good'}
            yield {'ip': '8.8.8.8', 'name': 'Bad'}
            raise OSError('multicast interrupted')
        self.adapter.discover.side_effect = discovery
        result = self.call('discover', brand='roku')
        self.assertTrue(result['ok'])
        self.assertEqual([d['ip'] for d in result['devices']], ['192.168.1.20'])
        self.assertTrue(result['warning'])

    def test_forget_removes_saved_credentials(self):
        ident = self.add()
        self.call('pair', id=ident)
        self.assertTrue(self.call('forget', id=ident)['ok'])
        self.assertEqual(self.call('list')['devices'], [])
        self.assertFalse(self.call('press', id=ident, key='home')['ok'])

    def test_network_actions_require_native_wifi_ip(self):
        result = json.loads(bridge.call('discover', '{"brand":"roku"}', self.temp.name, ''))
        self.assertFalse(result['ok'])
        self.adapter.discover.assert_not_called()


    def test_power_uses_wake_capable_method(self):
        ident = self.add()
        self.assertTrue(self.call('press', id=ident, key='power')['ok'])
        self.adapter.power.assert_called_once()
        self.adapter.press.assert_not_called()

    def test_google_commands_run_on_asyncio_thread(self):
        import asyncio
        import threading
        ids = []
        remote = Mock()
        remote.send_key_command.side_effect = lambda code: ids.append(threading.get_ident())
        remote.send_text.side_effect = lambda text: ids.append(threading.get_ident())
        caller = threading.get_ident()
        with patch.object(bridge.adapters.GoogleTV, '_get_remote', return_value=remote):
            bridge.adapters.GoogleTV.press({'ip': '192.168.1.20', 'paired': True}, 'home')
            bridge.adapters.GoogleTV.send_text({'ip': '192.168.1.20', 'paired': True}, 'hello')
        self.assertEqual(len(ids), 2)
        self.assertNotIn(caller, ids)
        self.assertEqual(ids[0], ids[1])

    def test_roku_literal_slash_is_encoded(self):
        with patch.object(bridge.adapters.Roku, 'request') as request:
            bridge.adapters.Roku.press({'ip': '192.168.1.20'}, 'lit:/')
        self.assertEqual(request.call_args.args[1], 'keypress/Lit_%2F')

    def test_adapter_urls_reject_external_targets(self):
        for url in ['http://8.8.8.8:8060/', 'http://localhost:8060/', 'file:///tmp/x', 'http://name@192.168.1.20:8060/']:
            with self.assertRaises(ValueError):
                bridge.adapters._validated_url(url)
        self.assertEqual(bridge.adapters._validated_url('http://192.168.1.20:8060/query'), 'http://192.168.1.20:8060/query')
        with self.assertRaises(ValueError):
            bridge.adapters._validated_url('ws://192.168.1.30:3000/', expected_host='192.168.1.20')

if __name__ == '__main__':
    unittest.main()
