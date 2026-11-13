import copy
import tempfile
import unittest
from pathlib import Path
from assistant import respond
from storage import Store


def protocol():
    state = {}
    for message in ['3', 'Тестовый дом', '20.11.2026', 'Дверь', 'Заменить дверь', '10', '8', '1', '1']:
        respond(state, message)
    return state


class Extensions(unittest.TestCase):
    def test_reopen_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.db'
            store = Store(path)
            state = {}
            respond(state, '1')
            store.save(state, 'a')
            store.close()
            store = Store(path)
            self.assertEqual(store.load('a'), state)
            self.assertEqual(store.load('b'), {})
            store.close()

    def test_edit_rejects_atomically(self):
        state = protocol()
        before = copy.deepcopy(state)
        self.assertIn('отклонено', respond(state, '/изменить yes 9'))
        self.assertEqual(before, state)
        respond(state, '/изменить date 31.02.2026')
        self.assertEqual(before, state)
        respond(state, '/изменить date 21.11.2026')
        self.assertIn('21.11.2026', state['result'])
        self.assertNotIn('20.11.2026', state['result'])

    def test_multiple_questions_and_old_edit(self):
        state = protocol()
        respond(state, '/вопрос')
        self.assertNotIn('done', state)
        for message in ['Лампы', 'Заменить лампы', '9', '7', '1', '1']:
            respond(state, message)
        self.assertIn('Вопрос 2', state['result'])
        respond(state, '/изменить 1.decision Починить дверь')
        self.assertIn('Починить дверь', state['result'])
        self.assertIn('Заменить лампы', state['result'])

    def test_empty_and_unknown_do_not_destroy_state(self):
        state = protocol()
        before = copy.deepcopy(state)
        respond(state, '')
        respond(state, '/нет')
        respond(state, 'меню')
        self.assertEqual(before, state)

    def test_vote_batch(self):
        state = protocol()
        respond(state, '/голоса 1 12 10 1 1')
        self.assertEqual(state['data']['present'], '12')
        before = copy.deepcopy(state)
        respond(state, '/голоса 1 12 11 1 1')
        self.assertEqual(before, state)

    def test_export_requires_completed_input(self):
        from exporter import export_draft
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                export_draft({}, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

if __name__ == '__main__':
    unittest.main()
