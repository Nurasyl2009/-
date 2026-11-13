"""Official Graph API client. Never include response bodies in errors."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class WhatsAppError(Exception):
    pass


class WhatsAppClient:
    def __init__(self, config):
        self.config = config

    def request(self, suffix='', payload=None):
        config = self.config
        url = 'https://graph.facebook.com/{}/{}{}'.format(
            config['WHATSAPP_API_VERSION'], config['WHATSAPP_PHONE_NUMBER_ID'], suffix)
        request = Request(url, data=None if payload is None else json.dumps(payload).encode('utf-8'),
                          headers={'Authorization': 'Bearer ' + config['WHATSAPP_ACCESS_TOKEN'],
                                   'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            code, subcode = None, None
            try:
                data = json.loads(error.read()).get('error', {})
                code, subcode = data.get('code'), data.get('error_subcode')
            except (ValueError, AttributeError):
                pass
            raise WhatsAppError(f'Meta HTTP {error.code}; code={code}; subcode={subcode}') from None
        except (URLError, TimeoutError, OSError):
            raise WhatsAppError('Не удалось соединиться с Meta. Проверьте сеть и повторите.') from None

    def check(self):
        return self.request('?fields=id')

    def send_text(self, recipient, text):
        if len(text) > 4096:
            raise ValueError('Текст превышает лимит одного сообщения.')
        return self.request('/messages', {'messaging_product': 'whatsapp', 'to': recipient,
                                         'type': 'text', 'text': {'body': text, 'preview_url': False}})
