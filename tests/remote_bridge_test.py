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

    def test_scan_remembers_every_tv_for_selector_after_restart(self):
        self.adapter.discover.return_value = [
            {'ip': '192.168.1.20', 'name': 'Upstairs'},
            {'ip': '192.168.1.21', 'name': 'Downstairs'},
            {'ip': '192.168.1.21', 'name': 'Duplicate'},
        ]
        result = self.call('discover', brand='roku')
        self.assertEqual(len(result['savedDevices']), 2)
        # A new bridge call reloads the on-disk list, as a restarted app does.
        saved = self.call('list')['devices']
        self.assertEqual([d['name'] for d in saved], ['Upstairs', 'Downstairs'])
        chosen = self.call('add', brand='roku', ip='192.168.1.20')['device']
        self.assertEqual(chosen['id'], saved[0]['id'])
        self.assertEqual(len(self.call('list')['devices']), 2)
        self.call('press', id=saved[1]['id'], key='home')
        self.assertEqual(self.adapter.press.call_args.args[0]['ip'], '192.168.1.21')

    def test_rescan_preserves_pairing_ids_and_unseen_tvs(self):
        ident = self.add()
        self.call('pair', id=ident)
        other = self.call('add', brand='roku', ip='192.168.1.22')['device']['id']
        self.adapter.discover.return_value = [{'ip': '192.168.1.20', 'name': 'Renamed TV'}]
        result = self.call('discover', brand='roku')
        self.assertEqual([d['id'] for d in result['savedDevices']], [ident, other])
        self.assertTrue(result['savedDevices'][0]['paired'])
        self.assertNotIn('secret', json.dumps(result))
        self.call('press', id=ident, key='home')
        self.assertEqual(self.adapter.press.call_args.args[0]['token'], 'secret')
        self.adapter.discover.side_effect = OSError('network interrupted')
        self.call('discover', brand='roku')
        self.assertEqual(len(self.call('list')['devices']), 2)

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

class RokuInputTests(unittest.TestCase):
    APPS = b'<apps><app id="12">Streaming app</app><app id="tvinput.hdmi1">Game console</app><app id="tvinput.dtv">Live TV</app><app id="tvinput.cvbs">AV</app><app id="tvinput.hdmi1">Duplicate</app><app id="tvinput.bad/path">Unsafe</app></apps>'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.request = patch.object(bridge.adapters.Roku, 'request', return_value=(self.APPS, 'text/xml'))
        self.mock_request = self.request.start()
        self.ident = self.call('add', brand='roku', ip='192.168.1.20')['device']['id']

    def tearDown(self):
        self.request.stop()
        self.temp.cleanup()

    def call(self, action, **payload):
        return json.loads(bridge.call(action, json.dumps(payload), self.temp.name, '192.168.1.5'))

    def test_lists_only_unique_safe_reported_tv_inputs(self):
        result = self.call('inputs', id=self.ident)
        self.assertTrue(result['ok'])
        self.assertEqual(result['inputs'], [
            {'id': 'tvinput.hdmi1', 'name': 'Game console'},
            {'id': 'tvinput.dtv', 'name': 'Live TV'},
            {'id': 'tvinput.cvbs', 'name': 'AV'},
        ])
        self.mock_request.assert_called_once_with(unittest.mock.ANY, 'query/apps')

    def test_selection_rechecks_allowlist_and_posts_launch(self):
        result = self.call('input', id=self.ident, input='tvinput.hdmi1')
        self.assertTrue(result['ok'])
        self.assertTrue(result['sent'])
        self.assertEqual([c.args[1] for c in self.mock_request.call_args_list], ['query/apps', 'launch/tvinput.hdmi1'])
        self.assertEqual(self.mock_request.call_args.kwargs, {'method': 'POST'})

    def test_rejects_invalid_and_unreported_input_ids_without_post(self):
        for value in ['12', 'tvinput.hdmi2', 'tvinput.hdmi1?x=1', 'tvinput.hdmi1/../../power', 'http://other/', '', None, 1, {}]:
            self.mock_request.reset_mock()
            result = self.call('input', id=self.ident, input=value)
            self.assertFalse(result['ok'], value)
            self.assertFalse(any(c.kwargs.get('method') == 'POST' for c in self.mock_request.call_args_list))

    def test_stick_or_unconfigured_tv_reports_clear_unsupported_error(self):
        self.mock_request.return_value = (b'<apps><app id="12">Streaming app</app></apps>', 'text/xml')
        result = self.call('inputs', id=self.ident)
        self.assertFalse(result['ok'])
        self.assertIn('Roku sticks', result['error'])
        self.assertIn('TV inputs', result['error'])

    def test_malformed_tv_response_is_not_treated_as_unsupported(self):
        self.mock_request.return_value = (b'<apps><broken', 'text/xml')
        result = self.call('inputs', id=self.ident)
        self.assertFalse(result['ok'])
        self.assertIn('read', result['error'])

    def test_disconnected_tv_does_not_send_selection(self):
        self.mock_request.side_effect = bridge.adapters.AdapterError('offline')
        result = self.call('input', id=self.ident, input='tvinput.hdmi1')
        self.assertFalse(result['ok'])
        self.assertEqual(self.mock_request.call_count, 1)

    def test_other_brands_keep_existing_input_key(self):
        fake = Mock(needs_pairing=False)
        with patch.dict(bridge.adapters.ADAPTERS, {'samsung': fake}):
            ident = self.call('add', brand='samsung', ip='192.168.1.21')['device']['id']
            self.assertFalse(self.call('inputs', id=ident)['ok'])
            self.assertFalse(self.call('input', id=ident, input='tvinput.hdmi1')['ok'])
            self.assertTrue(self.call('press', id=ident, key='input')['ok'])
            fake.press.assert_called_once_with(unittest.mock.ANY, 'input')

if __name__ == '__main__':
    unittest.main()
