"""Read-only access check. Does not send messages."""
from whatsapp_config import load_config, validate
from whatsapp_client import WhatsAppClient, WhatsAppError


def main():
    try:
        config = load_config()
        validate(config)
        print('Локальные настройки найдены. Секреты скрыты.')
        result = WhatsAppClient(config).check()
        if result.get('id') != config['WHATSAPP_PHONE_NUMBER_ID']:
            print('Ответ не подтвердил ожидаемый ID номера.')
            return 1
        print('Доступ к номеру подтверждён Meta. Сообщения не отправлялись.')
        missing = [key for key in ('WHATSAPP_APP_SECRET', 'WHATSAPP_VERIFY_TOKEN', 'WHATSAPP_ALLOWED_SENDERS') if not config.get(key)]
        if missing:
            print('Для входящих сообщений ещё нужны: ' + ', '.join(missing))
        return 0
    except (ValueError, OSError, WhatsAppError) as error:
        print(str(error) if not isinstance(error, OSError) else 'Не удалось прочитать настройки.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
