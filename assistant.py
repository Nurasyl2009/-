"""Local OSI workflow prototype. No AI or external delivery is enabled."""
from pathlib import Path

FLOWS = {
    '1': ('Объявление', [('event', 'Что произойдёт?'), ('address', 'Адрес и подъезд?'), ('date', 'Точная дата (дд.мм.гггг)?'), ('time', 'Время начала и окончания?'), ('action', 'Что нужно сделать жителям?')]),
    '2': ('Ответ жителю', [('question', 'Вставьте обращение жителя без персональных данных.'), ('facts', 'Какие факты подтверждены? Если неизвестно, напишите «неизвестно».'), ('next', 'Какое действие вы готовы подтвердить? Если никаких, напишите «неизвестно».')]),
    '3': ('Проект протокола', [('address', 'Адрес дома?'), ('date', 'Дата собрания (дд.мм.гггг)?'), ('agenda', 'Один вопрос повестки?'), ('decision', 'Точная формулировка решения?'), ('present', 'Сколько участников голосовало по этому вопросу?'), ('yes', 'Голосов «за»?'), ('no', 'Голосов «против»?'), ('abstain', 'Воздержались?')]),
}
MENU = 'Помощник ОСИ • тестовый режим\n1 — объявление\n2 — ответ жителю\n3 — проект протокола\n/сброс — начать заново\nТексты собираются по шаблонам. Не вводите реальные персональные данные.'

def render(kind, d):
    if kind == '1':
        return f"Уважаемые жители!\n\n{d['date']}, {d['time']}, по адресу {d['address']}: {d['event']}.\n\n{d['action']}\n\nПросим учитывать эту информацию при планировании."
    if kind == '2':
        facts = 'Информация по вашему вопросу пока не подтверждена.' if d['facts'].lower() == 'неизвестно' else d['facts']
        follow = 'Срок решения пока не установлен.' if d['next'].lower() == 'неизвестно' else d['next']
        return f"Здравствуйте! Спасибо за обращение.\n\n{facts}\n\n{follow}"
    issues = d.get('issues', []) + [d]
    agenda = '\n\n'.join(
        f"Вопрос {i}: {item['agenda']}\nФормулировка: {item['decision']}\n"
        f"Участников голосования: {item['present']}; за: {item['yes']}; "
        f"против: {item['no']}; воздержались: {item['abstain']}."
        for i, item in enumerate(issues, 1))
    return (f"ПРОЕКТ — НЕ ГОТОВ ДЛЯ ПОДПИСАНИЯ\nРабочая сводка для заполнения официальной формы явочного собрания.\n\n"
            f"Дом: {d['address']}\nДата: {d['date']}\n\n{agenda}\n\n"
            "Необходимо заполнить по официальной форме: номер, время, инициатора, сведения о собственниках, "
            "председателе и секретаре собрания, список участников, приложения и подписи.\n"
            "Правомочность собрания и принятие решения не определялись.\n"
            "Источник формы: https://old.adilet.zan.kz/rus/docs/V2600039329")

def _respond(state, message):
    from datetime import datetime
    message = message.strip()
    if message.lower() in ('/start', '/сброс', '/reset'):
        state.clear()
        return MENU
    if 'kind' not in state:
        if message not in FLOWS:
            return MENU
        state.update(kind=message, step=0, data={})
        return FLOWS[message][1][0][1]
    if state.get('done'):
        return 'Для новой задачи отправьте /сброс.\n\n' + state['result']
    kind = state['kind']
    fields = FLOWS[kind][1]
    key = fields[state['step']][0]
    if len(message) > 2000:
        return 'Пожалуйста, сократите ответ до 2000 символов.'
    if key == 'date':
        try:
            datetime.strptime(message, '%d.%m.%Y')
        except ValueError:
            return 'Нужна существующая точная дата в формате дд.мм.гггг.'
    if key in ('present', 'yes', 'no', 'abstain'):
        if not message.isascii() or not message.isdigit() or int(message) > 100000:
            return 'Введите целое неотрицательное число до 100000.'
        if key == 'present' and int(message) == 0:
            return 'Число участников голосования должно быть больше нуля.'
    state['data'][key] = message
    if key == 'abstain':
        d = state['data']
        if sum(int(d[k]) for k in ('yes', 'no', 'abstain')) != int(d['present']):
            state['step'] = 4
            return 'Сумма голосов не совпадает с числом участников. Повторим четыре числа. Сколько участников голосовало?'
    state['step'] += 1
    if state['step'] < len(fields):
        return fields[state['step']][1]
    result = render(kind, state['data'])
    state.update(done=True, result=result)
    return 'Черновик. Проверьте сведения перед использованием.\n\n' + result


def respond(state, message):
    """Transport-independent dialogue; edits are validated before committing."""
    from copy import deepcopy
    message = message.strip()
    if not message:
        return 'Пустой ответ. Введите текст или /помощь.'
    if any(ord(c) < 32 and c not in '\n\t' for c in message):
        return 'Удалите управляющие символы из сообщения.'
    if message.lower() in ('/помощь', 'меню'):
        return MENU + '\n/поля — значения\n/изменить поле значение — исправление\n/вопрос — добавить вопрос протокола\n/экспорт — TXT и Word\n/выход — сохранить диалог и выйти'
    if message == '/поля':
        if 'kind' not in state:
            return MENU
        return '\n'.join(f"{key}: {state['data'].get(key, '—')}" for key, _ in FLOWS[state['kind']][1]) + '\nВ протоколе показан последний вопрос. Старые вопросы: /изменить N.поле значение.'
    if message.startswith('/изменить'):
        parts = message.split(maxsplit=2)
        if len(parts) != 3 or not state.get('done'):
            return 'После завершения черновика: /изменить поле новое значение. Список: /поля.'
        _, target, value = parts
        candidate = deepcopy(state)
        fields = FLOWS[state['kind']][1]
        keys = [key for key, _ in fields]
        issue_index = None
        if '.' in target:
            prefix, target = target.split('.', 1)
            if state['kind'] != '3' or not prefix.isascii() or not prefix.isdigit() or target not in keys[2:]:
                return 'Неверный номер вопроса или поле.'
            issue_index = int(prefix) - 1
            issues = candidate['data'].get('issues', [])
            if issue_index < 0 or issue_index > len(issues):
                return 'Такого вопроса нет.'
            if issue_index < len(issues):
                for key in keys[2:]:
                    candidate['data'][key] = issues[issue_index][key]
        if target not in keys:
            return 'Неизвестное поле. Отправьте /поля.'
        candidate.pop('done', None)
        candidate['step'] = keys.index(target)
        answer = _respond(candidate, value)
        if candidate['data'].get(target) != value or candidate['step'] != keys.index(target) + 1:
            return answer
        d = candidate['data']
        if state['kind'] == '3' and sum(int(d[k]) for k in ('yes', 'no', 'abstain')) != int(d['present']):
            return 'Изменение отклонено: сумма голосов не совпадает. Используйте /голоса N участников за против воздержались.'
        if issue_index is not None and issue_index < len(d.get('issues', [])):
            edited = {key: d[key] for key in keys[2:]}
            candidate['data'] = deepcopy(state['data'])
            candidate['data']['issues'][issue_index] = edited
        candidate.update(done=True, step=len(fields), result=render(state['kind'], candidate['data']))
        state.clear()
        state.update(candidate)
        return 'Черновик обновлён.\n\n' + state['result']
    if message.startswith('/голоса'):
        parts = message.split()
        if state.get('kind') != '3' or not state.get('done') or len(parts) != 6:
            return 'После завершения протокола: /голоса N участников за против воздержались.'
        if any(not x.isascii() or not x.isdigit() or len(x) > 6 for x in parts[1:]):
            return 'Введите целые неотрицательные числа.'
        number, present, yes, no, abstain = map(int, parts[1:])
        issues = state['data'].get('issues', [])
        if not 1 <= number <= len(issues) + 1:
            return 'Такого вопроса нет.'
        if not 1 <= present <= 100000 or yes + no + abstain != present:
            return 'Изменение отклонено: проверьте число участников и сумму голосов.'
        target = issues[number - 1] if number <= len(issues) else state['data']
        target.update(zip(('present', 'yes', 'no', 'abstain'), map(str, (present, yes, no, abstain))))
        state['result'] = render('3', state['data'])
        return 'Итоги обновлены.\n\n' + state['result']
    if message == '/вопрос':
        if state.get('kind') != '3' or not state.get('done'):
            return 'Сначала завершите текущий вопрос протокола.'
        d = state['data']
        d.setdefault('issues', []).append({key: d.pop(key) for key, _ in FLOWS['3'][1][2:]})
        state.pop('done', None)
        state.pop('result', None)
        state['step'] = 2
        return 'Следующий вопрос повестки?'
    if message.startswith('/') and message not in ('/start', '/сброс', '/reset'):
        return 'Неизвестная команда. Отправьте /помощь.'
    return _respond(state, message)

def main():
    from assistant_service import respond, HELP
    from storage import Store
    from exporter import export_draft
    store = Store(Path(__file__).parent / 'work' / 'assistant.sqlite3')
    state = store.load()
    print('Сохранённый диалог восстановлен. /поля или /сброс.' if state else HELP)
    while True:
        try:
            message = input('\nВы: ')
        except (EOFError, KeyboardInterrupt):
            break
        if message == '/выход':
            break
        if message == '/экспорт':
            try:
                paths = export_draft(state, Path(__file__).parent / 'work' / 'drafts')
                print('Сохранено:', ', '.join(str(p) for p in paths))
            except (ValueError, ImportError, OSError) as error:
                print('Экспорт не выполнен:', error)
            continue
        print('\nПомощник:', respond(state, message))
        store.save(state)
    store.close()

if __name__ == '__main__':
    main()
