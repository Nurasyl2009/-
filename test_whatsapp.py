import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from storage import Store
from whatsapp_config import load_config, validate
from whatsapp_server import signature_valid, incoming, initialize, enqueue


class WhatsAppTests(unittest.TestCase):
    def test_http_rejects_unsigned_and_accepts_verified_payload(self):
        import threading
        from http.server import HTTPServer
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from whatsapp_server import handler
        config = {'WHATSAPP_APP_SECRET': 'fake', 'WHATSAPP_VERIFY_TOKEN': 'verify',
                  'WHATSAPP_PHONE_NUMBER_ID': '123', 'WHATSAPP_ALLOWED_SENDERS': '77000000000'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.db'
            initialize(path)
            server = HTTPServer(('127.0.0.1', 0), handler(config, path))
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            base = 'http://127.0.0.1:' + str(server.server_port)
            try:
                with urlopen(base + '/webhook?hub.mode=subscribe&hub.verify_token=verify&hub.challenge=42') as response:
                    self.assertEqual(response.read(), b'42')
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + '/webhook', data=b'{}'))
                self.assertEqual(error.exception.code, 403)
                signature = 'sha256=' + hmac.new(b'fake', b'{}', hashlib.sha256).hexdigest()
                with urlopen(Request(base + '/webhook', data=b'{}', headers={'X-Hub-Signature-256': signature})) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_signature(self):
        body = b'{"test":true}'
        signature = 'sha256=' + hmac.new(b'fake-secret', body, hashlib.sha256).hexdigest()
        self.assertTrue(signature_valid(body, signature, 'fake-secret'))
        self.assertFalse(signature_valid(body + b' ', signature, 'fake-secret'))
        self.assertFalse(signature_valid(body, '', 'fake-secret'))

    def test_filter_and_duplicates(self):
        config = {'WHATSAPP_PHONE_NUMBER_ID': '123', 'WHATSAPP_ALLOWED_SENDERS': '77000000000'}
        message = {'from': '77000000000', 'id': 'test-id', 'timestamp': str(int(time.time())), 'type': 'text', 'text': {'body': '/start'}}
        payload = {'object': 'whatsapp_business_account', 'entry': [{'changes': [{'value': {'metadata': {'phone_number_id': '123'}, 'messages': [message]}}]}]}
        jobs = list(incoming(payload, config))
        self.assertEqual(len(jobs), 1)
        message['from'] = 'other'
        self.assertEqual(list(incoming(payload, config)), [])
        message['from'] = '77000000000'
        message['timestamp'] = '1'
        self.assertEqual(list(incoming(payload, config)), [])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.db'
            initialize(path)
            store = Store(path)
            enqueue(store.db, jobs + jobs)
            self.assertEqual(store.db.execute('SELECT count(*) FROM jobs').fetchone()[0], 1)
            store.close()

    def test_dotenv_bom_quotes_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('\ufeffWHATSAPP_ACCESS_TOKEN="fake"\nWHATSAPP_PHONE_NUMBER_ID=123\n', encoding='utf-8')
            config = load_config(path)
            validate(config)
            with self.assertRaises(ValueError):
                validate(config, webhook=True)


if __name__ == '__main__':
    unittest.main()
