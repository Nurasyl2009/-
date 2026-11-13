"""Shared AI/workflow routing for desktop, console, and WhatsApp."""
from assistant import respond as template_respond
from ai_client import AIClient, AIError

HELP = ('Помощник ОСИ • ИИ и документы\n'
        'Напишите вопрос обычным текстом — ответит языковая модель.\n'
        '1 — объявление; 2 — ответ жителю; 3 — сводка протокола.\n'
        '/ии — свободный диалог; /шаблоны — пошаговые документы.\n'
        '/улучшить — предложить редакцию готового черновика.\n'
        '/сброс — очистить диалог; /помощь — команды.\n'
        'По умолчанию модель работает локально через Ollama. Ответы ИИ требуют проверки.')


def respond(state, message, client=None):
    message = message.strip()
    if not message:
        return 'Введите вопрос или /помощь.'
    if len(message) > 6000:
        return 'Сократите сообщение до 6000 символов.'
    if any(ord(c) < 32 and c not in '\n\t' for c in message):
        return 'Удалите управляющие символы из сообщения.'
    command = message.lower()
    if command in ('/start', '/сброс', '/reset'):
        state.clear()
        return HELP
    if command in ('/помощь', 'меню'):
        return HELP + '\n\n' + template_respond({}, '/помощь')
    if command == '/ии':
        state['mode'] = 'ai'
        return 'ИИ-диалог включён. Напишите вопрос. Черновик сохранён; вернуться: /шаблоны.'
    if command == '/шаблоны':
        state['mode'] = 'templates'
        return template_respond(state, '/помощь')
    improving = command == '/улучшить'
    if improving and not state.get('done'):
        return 'Сначала завершите черновик в режиме шаблонов.'
    if not improving and (command.startswith('/') or
                          (state.get('mode') != 'ai' and ('kind' in state or message in ('1', '2', '3')))):
        return template_respond(state, message)
    if state.get('mode') == 'templates' and not improving:
        return template_respond(state, message)
    prompt = ('Отредактируй этот черновик: улучши ясность, сохрани все факты, числа и оговорки. '
              'Не добавляй сведений.\n\n' + state['result']) if improving else message
    history = [] if improving else list(state.get('ai_history', []))[-12:]
    while history and sum(len(item['content']) for item in history) > 18000:
        history = history[2:]
    messages = history + [{'role': 'user', 'content': prompt}]
    try:
        answer = (client or AIClient()).complete(messages)
    except AIError as error:
        return 'Не удалось получить ответ ИИ: ' + str(error)
    state['ai_last'] = answer
    if not improving:
        state['ai_history'] = (messages + [{'role': 'assistant', 'content': answer}])[-12:]
    return ('Предложенная редакция ИИ. Исходный черновик сохранён.\n\n' if improving else '') + answer
