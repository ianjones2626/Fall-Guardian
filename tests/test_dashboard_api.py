"""API smoke tests; no Raspberry Pi or microphone required."""

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import importlib.util
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


MODULE_PATH = Path(__file__).resolve().parents[1] / 'dashboard' / 'server.py'
spec = importlib.util.spec_from_file_location('fallguardian_dashboard_server', MODULE_PATH)
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)


class DashboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server_module.DashboardHandler)
        cls.base = f'http://127.0.0.1:{cls.httpd.server_port}'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        with server_module.STATE_LOCK:
            server_module.INCIDENTS.clear()
            server_module.LAST_HEARTBEAT = None
            server_module.LIVE_INPUT_SEEN = False
            server_module.HEARTBEAT.update(camera_online=False, monitoring_active=False, people_visible=0)

    def get_state(self):
        with urlopen(self.base + '/api/state', timeout=2) as response:
            return json.load(response)

    def post(self, path, value, expected=200):
        request = Request(self.base + path, data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, expected)
                return json.load(response)
        except HTTPError as error:
            self.assertEqual(error.code, expected)
            return json.loads(error.read())

    def test_status_requires_fresh_detector_heartbeat(self):
        self.assertEqual(self.get_state()['camera_status'], 'offline')
        self.assertEqual(self.get_state()['safety_status'], 'unknown')
        self.post('/api/heartbeat', {'camera_online': True, 'monitoring_active': True, 'people_visible': 2})
        state = self.get_state()
        self.assertEqual(state['camera_status'], 'online')
        self.assertEqual(state['people_visible'], 2)
        with server_module.STATE_LOCK:
            server_module.LAST_HEARTBEAT = time.monotonic() - 20
        self.assertEqual(self.get_state()['camera_status'], 'offline')

    def test_fall_escalation_and_voice_safe(self):
        event = {'event_type': 'fall_detected', 'event_id': 'test-person-1', 'person_id': 1, 'source': 'fall_detector', 'reason': 'Lying posture detected', 'demo': False}
        first = self.post('/api/events', event, 201)
        self.assertEqual(first['incident']['status'], 'active')
        self.post('/api/events', event, 201)
        self.assertEqual(len(self.get_state()['incidents']), 1)
        self.post('/api/events', {'event_type': 'caregiver_alert', 'event_id': event['event_id'], 'reason': 'No response'})
        self.assertEqual(self.get_state()['active_alert']['status'], 'escalated')
        self.post('/api/events', {'event_type': 'person_safe', 'event_id': event['event_id']})
        state = self.get_state()
        self.assertIsNone(state['active_alert'])
        self.assertEqual(state['incidents'][0]['resolution'], 'Voice confirmed safe')

    def test_manual_simulation_acknowledgement_and_clear(self):
        result = self.post('/api/events', {'event_type': 'fall_detected', 'source': 'demo'}, 201)
        event_id = result['incident']['event_id']
        self.assertTrue(result['incident']['demo'])
        self.post('/api/alerts/acknowledge', {})
        self.assertEqual(self.get_state()['active_alert']['status'], 'acknowledged')
        self.post('/api/events', {'event_type': 'manual_clear', 'event_id': event_id})
        self.assertIsNone(self.get_state()['active_alert'])

    def test_multiple_alerts_keep_older_unresolved_event(self):
        self.post('/api/events', {'event_type':'fall_detected','event_id':'one'}, 201)
        self.post('/api/events', {'event_type':'fall_detected','event_id':'two'}, 201)
        self.post('/api/events', {'event_type':'person_safe','event_id':'two'})
        self.assertEqual(self.get_state()['active_alert']['event_id'], 'one')

    def test_rejects_malformed_payloads(self):
        self.post('/api/events', {'event_type':'invalid'}, 400)
        self.post('/api/heartbeat', {'camera_online':'yes','monitoring_active':True}, 400)
        self.post('/api/events', {'event_type':'person_safe','event_id':'missing'}, 404)


if __name__ == '__main__':
    unittest.main()
