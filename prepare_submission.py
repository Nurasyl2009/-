"""Rebuild local practice evidence and a source-only submission archive."""
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from assistant import respond

ROOT = Path(__file__).resolve().parent


def main():
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    cases = [
        ('Объявление', ['1', 'плановая проверка освещения', 'Учебный дом, подъезд 1',
                         '16.11.2026', '10:00–12:00', 'Обеспечьте доступ к щитку']),
        ('Ответ жителю', ['2', 'Когда заменят лампу?', 'Заявка о неисправной лампе принята.',
                          'Передадим заявку электрику 16.11.2026.']),
        ('Рабочая сводка протокола', ['3', 'Учебный дом', '13.11.2026', 'Освещение подъезда',
                                     'Заменить неисправные лампы', '10', '8', '1', '1']),
    ]
    lines = ['Демонстрация на вымышленных данных. Дата отчёта: 13.11.2026.',
             'Все ответы получены вызовами реального обработчика respond().']
    for title, messages in cases:
        state = {}
        lines.append('\n=== ' + title + ' ===')
        for message in messages:
            answer = respond(state, message)
            lines.extend(['\nПользователь: ' + message, 'Помощник: ' + answer])
        if not state.get('done'):
            raise RuntimeError('Не завершён сценарий: ' + title)
    (reports / 'demo.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    result = subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    (reports / 'test-results.txt').write_text(
        'Command: python -m unittest -v\nExit code: ' + str(result.returncode) + '\n'
        + result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise SystemExit(result.returncode)
    # Explicit allowlist: never package .env, SQLite, conversations, or tools.
    sources = ['assistant.py', 'storage.py', 'exporter.py', 'whatsapp_client.py',
               'whatsapp_config.py', 'whatsapp_server.py', 'check_whatsapp.py',
               'test_assistant.py', 'test_extensions.py', 'test_whatsapp.py',
               'requirements.txt', 'README.md', 'WHATSAPP_SETUP.md', '.gitignore',
               'prepare_submission.py', 'ai_client.py', 'assistant_service.py',
               'desktop_app.py', 'start_assistant.bat', 'AI_SETUP.md', 'test_ai.py']
    evidence = ['2026-11-13.md', 'COPY_TO_REPORT.txt', 'SPRINT_PLAN.md',
                'demo.txt', 'test-results.txt', 'connection-check.txt', 'AI_PROGRESS.md']
    output = ROOT / 'submission'
    output.mkdir(exist_ok=True)
    target = output / 'osi-practice-2026-11-13.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for name in sources:
            archive.write(ROOT / name, name)
        for name in evidence:
            archive.write(reports / name, 'reports/' + name)
    with ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Archive verification failed')
        print('Archive checked:', len(archive.namelist()), 'files')
    print(target)


if __name__ == '__main__':
    main()
