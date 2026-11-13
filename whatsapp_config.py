"""Load local credentials without logging their contents."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_config(path=None):
    values = {}
    path = Path(path) if path else ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.partition('=')
            if not separator:
                raise ValueError('В .env есть строка без знака =')
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '\"\'':
                value = value[1:-1]
            values[key.strip()] = value
    for key in ('WHATSAPP_ACCESS_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID', 'WHATSAPP_API_VERSION',
                'WHATSAPP_APP_SECRET', 'WHATSAPP_VERIFY_TOKEN', 'WHATSAPP_ALLOWED_SENDERS'):
        if key in os.environ:
            values[key] = os.environ[key]
    values.setdefault('WHATSAPP_API_VERSION', 'v23.0')
    return values


def validate(config, webhook=False):
    required = ['WHATSAPP_ACCESS_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID']
    if webhook:
        required += ['WHATSAPP_APP_SECRET', 'WHATSAPP_VERIFY_TOKEN', 'WHATSAPP_ALLOWED_SENDERS']
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise ValueError('Не заполнены: ' + ', '.join(missing))
    if not re.fullmatch(r'[0-9]+', config['WHATSAPP_PHONE_NUMBER_ID']):
        raise ValueError('WHATSAPP_PHONE_NUMBER_ID должен содержать только цифры без пробелов.')
    if not re.fullmatch(r'v[0-9]+\.0', config['WHATSAPP_API_VERSION']):
        raise ValueError('Неверный формат WHATSAPP_API_VERSION.')
    if any(c.isspace() for c in config['WHATSAPP_ACCESS_TOKEN']):
        raise ValueError('В токене обнаружены пробелы или переносы.')
