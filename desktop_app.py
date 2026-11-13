"""Local desktop chat; model requests run outside the UI thread."""
from copy import deepcopy
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from assistant_service import HELP, respond
from storage import Store

ROOT = Path(__file__).resolve().parent


def main():
    root = tk.Tk()
    root.title('Помощник ОСИ — локальный ИИ')
    root.geometry('900x720')
    store = Store(ROOT / 'work' / 'desktop.sqlite3')
    state = store.load()
    results = queue.Queue()
    busy = False
    tk.Label(root, text='Помощник ОСИ', font=('Segoe UI', 22, 'bold')).pack(anchor='w', padx=18, pady=(12, 0))
    tk.Label(root, text='Локальная модель • диалоги • объявления • черновики документов',
             font=('Segoe UI', 10)).pack(anchor='w', padx=18, pady=(0, 10))
    chat = scrolledtext.ScrolledText(root, wrap='word', font=('Segoe UI', 11), state='disabled')
    chat.pack(fill='both', expand=True, padx=18)

    def append(who, text):
        chat.configure(state='normal')
        chat.insert('end', who + '\n' + text + '\n\n')
        chat.configure(state='disabled')
        chat.see('end')

    append('Помощник', HELP)
    for item in state.get('ai_history', []):
        append('Вы' if item['role'] == 'user' else 'Помощник', item['content'])
    status = tk.StringVar(value='Готов к работе')
    tk.Label(root, textvariable=status).pack(anchor='w', padx=18)
    entry = tk.Text(root, height=4, wrap='word', font=('Segoe UI', 11))
    entry.pack(fill='x', padx=18)
    buttons = tk.Frame(root)
    buttons.pack(fill='x', padx=18, pady=12)

    def send(text=None):
        nonlocal busy
        if busy:
            return
        text = text if text is not None else entry.get('1.0', 'end').strip()
        if not text:
            return
        busy = True
        send_button.configure(state='disabled')
        entry.delete('1.0', 'end')
        append('Вы', text)
        status.set('Модель готовит ответ… Первый запуск может занять несколько минут.')
        candidate = deepcopy(state)

        def work():
            try:
                results.put((candidate, respond(candidate, text)))
            except Exception:
                results.put((None, 'Ошибка обработки. Сохранённый диалог не изменён.'))
        threading.Thread(target=work, daemon=True).start()

    def poll():
        nonlocal busy, state
        try:
            candidate, answer = results.get_nowait()
        except queue.Empty:
            pass
        else:
            if candidate is not None:
                try:
                    store.save(candidate)
                    state = candidate
                except Exception:
                    answer += '\n[Не удалось сохранить диалог на диск.]'
            append('Помощник', answer)
            busy = False
            send_button.configure(state='normal')
            status.set('Готов к работе')
        root.after(100, poll)

    def save_text():
        text = state.get('ai_last') or state.get('result')
        if not text:
            messagebox.showinfo('Экспорт', 'Сначала получите ответ или создайте черновик.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Текст', '*.txt')])
        if path:
            try:
                Path(path).write_text(text, encoding='utf-8')
            except OSError:
                messagebox.showerror('Экспорт', 'Не удалось сохранить файл.')

    send_button = tk.Button(buttons, text='Отправить', command=send)
    send_button.pack(side='left')
    for label, command in [('ИИ-диалог', '/ии'), ('Шаблоны', '/шаблоны'), ('Новый диалог', '/сброс')]:
        tk.Button(buttons, text=label, command=lambda c=command: send(c)).pack(side='left', padx=5)
    tk.Button(buttons, text='Сохранить ответ TXT', command=save_text).pack(side='right')
    entry.bind('<Control-Return>', lambda event: send())

    def close():
        if busy and not messagebox.askyesno('Закрыть?', 'Ответ ещё готовится. Закрыть без сохранения этого ответа?'):
            return
        store.close()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    poll()
    root.mainloop()


if __name__ == '__main__':
    main()
