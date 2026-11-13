"""Local pilot webhook. Bind only to localhost, expose through an HTTPS tunnel.

Incoming payloads require Meta HMAC and a sender allowlist. Jobs are persisted
before acknowledgement. Failed or uncertain sends are NOT automatically retried.
"""
import hashlib
import hmac
import json
import sqlite3
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit, parse_qs

from assistant_service import respond
from storage import Store
from whatsapp_config import ROOT, load_config, validate
from whatsapp_client import WhatsAppClient, WhatsAppError

DB = ROOT / 'work' / 'whatsapp.sqlite3'


def signature_valid(body, signature, secret):
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature)


def incoming(payload, config):
    allowed = {s.strip() for s in config['WHATSAPP_ALLOWED_SENDERS'].split(',')}
    if payload.get('object') != 'whatsapp_business_account':
        return
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            if value.get('metadata', {}).get('phone_number_id') != config['WHATSAPP_PHONE_NUMBER_ID']:
                continue
            for message in value.get('messages', []):
                sender = message.get('from', '')
                if sender not in allowed or not message.get('id'):
                    continue
                timestamp = int(message.get('timestamp', 0))
                if not 0 <= time.time() - timestamp < 23 * 3600:
                    continue
                body = message.get('text', {}).get('body') if message.get('type') == 'text' else None
                yield message['id'], sender, body, timestamp


def initialize(path):
    store = Store(path)
    store.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, sender TEXT, body TEXT, received INTEGER, status TEXT, reply TEXT)')
    # A crash during a send leaves an uncertain delivery: never blindly resend.
    store.db.execute("UPDATE jobs SET status='uncertain' WHERE status='sending'")
    store.db.commit()
    store.close()


def enqueue(db, jobs):
    with db:
        for mid, sender, body, timestamp in jobs:
            db.execute('INSERT OR IGNORE INTO jobs VALUES (?, ?, ?, ?, ?, NULL)',
                       (mid, sender, body, timestamp, 'pending'))


def worker(config, stop, path=DB):
    store = Store(path)
    client = WhatsAppClient(config)
    while not stop.is_set():
        row = store.db.execute("SELECT id, sender, body, received FROM jobs WHERE status='pending' ORDER BY rowid LIMIT 1").fetchone()
        if not row:
            stop.wait(.5)
            continue
        mid, sender, body, received = row
        if time.time() - received >= 23 * 3600:
            with store.db:
                store.db.execute("UPDATE jobs SET status='expired' WHERE id=?", (mid,))
            continue
        try:
            state = store.load('wa:' + sender)
            if body is None:
                reply = 'Пока поддерживаются только текстовые сообщения. Отправьте /start.'
            elif body.strip() == '/экспорт':
                reply = 'Отправка файлов через WhatsApp пока не подключена. Черновик доступен здесь текстом.'
            else:
                reply = respond(state, body)
            # Persist state and claim the send atomically before any network call.
            with store.db:
                payload = json.dumps({'version': 1, 'state': state}, ensure_ascii=False)
                store.db.execute('INSERT INTO sessions VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', ('wa:' + sender, payload))
                store.db.execute("UPDATE jobs SET status='sending', reply=? WHERE id=?", (reply, mid))
            for offset in range(0, len(reply), 3500):
                client.send_text(sender, reply[offset:offset + 3500])
            with store.db:
                store.db.execute("UPDATE jobs SET status='sent' WHERE id=?", (mid,))
        except WhatsAppError as error:
            with store.db:
                store.db.execute("UPDATE jobs SET status='uncertain' WHERE id=?", (mid,))
            print('Ответ не подтверждён. Автоповтора нет:', error, flush=True)
        except Exception:
            with store.db:
                store.db.execute("UPDATE jobs SET status='failed' WHERE id=?", (mid,))
            print('Ошибка обработки задания; содержимое и секреты скрыты.', flush=True)
    store.close()


def handler(config, path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Query strings can contain the verification token.

        def reply(self, status, body=''):
            data = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/health':
                return self.reply(200, 'ok')
            if url.path != '/webhook':
                return self.reply(404)
            query = parse_qs(url.query)
            if query.get('hub.mode') == ['subscribe'] and hmac.compare_digest(query.get('hub.verify_token', [''])[0], config['WHATSAPP_VERIFY_TOKEN']):
                return self.reply(200, query.get('hub.challenge', [''])[0])
            self.reply(403)

        def do_POST(self):
            if urlsplit(self.path).path != '/webhook':
                return self.reply(404)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024 * 1024:
                    return self.reply(413)
                self.connection.settimeout(10)
                body = self.rfile.read(size)
                if not signature_valid(body, self.headers.get('X-Hub-Signature-256', ''), config['WHATSAPP_APP_SECRET']):
                    return self.reply(403)
                jobs = list(incoming(json.loads(body), config))
            except (ValueError, TypeError, AttributeError, TimeoutError):
                return self.reply(400)
            try:
                with closing(sqlite3.connect(path)) as db:
                    enqueue(db, jobs)
            except sqlite3.Error:
                return self.reply(503)
            self.reply(200, 'EVENT_RECEIVED')
    return Handler


def main():
    config = load_config()
    validate(config, webhook=True)
    senders = config['WHATSAPP_ALLOWED_SENDERS'].split(',')
    if any(not s.strip().isascii() or not s.strip().isdigit() for s in senders):
        raise ValueError('Разрешённые номера: только цифры с кодом страны, через запятую.')
    initialize(DB)
    stop = threading.Event()
    server = HTTPServer(('127.0.0.1', 8080), handler(config, DB))
    thread = threading.Thread(target=worker, args=(config, stop), daemon=True)
    thread.start()
    print('WhatsApp pilot: http://127.0.0.1:8080/webhook — требуется публичный HTTPS tunnel.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        thread.join(timeout=25)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError):
        print('Сервер не запущен. Проверьте .env и доступность порта 8080. См. WHATSAPP_SETUP.md.')
        raise SystemExit(1)
