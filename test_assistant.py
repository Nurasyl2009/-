import unittest
from assistant import respond

class Workflows(unittest.TestCase):
    def run_flow(self, messages):
        state = {}
        for message in messages:
            result = respond(state, message)
        return state, result

    def test_announcement(self):
        state, result = self.run_flow(['1', 'ремонт', 'Тестовый дом', '20.11.2026', '10–12', 'Запаситесь водой'])
        self.assertTrue(state['done'])
        self.assertIn('20.11.2026', result)

    def test_missing_facts(self):
        _, result = self.run_flow(['2', 'Когда ремонт?', 'неизвестно', 'неизвестно'])
        self.assertIn('не установлен', result)

    def test_votes(self):
        state, result = self.run_flow(['3', 'Дом', '20.11.2026', 'Ремонт', 'Заменить дверь', '10', '8', '1', '0'])
        self.assertNotIn('done', state)
        self.assertIn('не совпадает', result)
        for text in ['10', '8', '1', '1']:
            result = respond(state, text)
        self.assertTrue(state['done'])
        self.assertIn('НЕ ГОТОВ', result)

    def test_date_and_reset(self):
        state, result = self.run_flow(['1', 'ремонт', 'Дом', '31.02.2026'])
        self.assertIn('существующая', result)
        respond(state, '/сброс')
        self.assertEqual(state, {})

    def test_isolation(self):
        a, b = {}, {}
        respond(a, '1')
        respond(a, 'Секретное событие')
        self.assertNotIn('Секретное', respond(b, '2'))

if __name__ == '__main__':
    unittest.main()
