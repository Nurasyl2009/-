import copy
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from ai_client import AIClient, AIError
from assistant_service import respond
from test_extensions import protocol


class Fake:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def complete(self, messages):
        self.calls.append(messages)
        if self.fail:
            raise AIError('test unavailable')
        return 'Проверенный тестовый ответ'


class AIIntegration(unittest.TestCase):
    def test_chat_history_and_reset(self):
        state, client = {}, Fake()
        respond(state, 'Первый вопрос', client)
        respond(state, 'Уточнение', client)
        self.assertEqual(len(client.calls[1]), 3)
        self.assertEqual(len(state['ai_history']), 4)
        respond(state, '/сброс', client)
        self.assertEqual(state, {})

    def test_error_preserves_state(self):
        state = {'ai_history': [{'role': 'user', 'content': 'old'}]}
        before = copy.deepcopy(state)
        self.assertIn('Не удалось', respond(state, 'Вопрос', Fake(True)))
        self.assertEqual(before, state)

    def test_template_does_not_call_model(self):
        state, client = {}, Fake()
        for message in ['1', 'ремонт', 'Дом', '16.11.2026', '10–12', 'Подготовьтесь']:
            respond(state, message, client)
        self.assertTrue(state['done'])
        self.assertEqual(client.calls, [])

    def test_improvement_keeps_original(self):
        state, client = protocol(), Fake()
        before = copy.deepcopy(state)
        respond(state, '/улучшить', client)
        self.assertEqual(state['result'], before['result'])
        self.assertEqual(state['data'], before['data'])
        self.assertIn(before['result'], client.calls[0][-1]['content'])

    def test_bounded_history_and_isolation(self):
        state, client = {}, Fake()
        for i in range(30):
            respond(state, str(i) + ' вопрос', client)
        self.assertLessEqual(len(state['ai_history']), 12)
        respond({}, 'Новый пользователь', client)
        self.assertEqual(len(client.calls[-1]), 1)

    def test_ollama_payload_and_response(self):
        response = io.BytesIO(json.dumps({'message': {'content': 'Ответ'}, 'done_reason': 'stop'}).encode())
        with patch('ai_client.urlopen', return_value=response) as request:
            self.assertEqual(AIClient({'AI_PROVIDER': 'ollama'}).complete([{'role': 'user', 'content': 'Вопрос'}]), 'Ответ')
        payload = json.loads(request.call_args.args[0].data)
        self.assertFalse(payload['stream'])
        self.assertFalse(payload['think'])
        self.assertEqual(payload['messages'][0]['role'], 'system')

    def test_http_error_does_not_expose_body_or_key(self):
        with patch('ai_client.urlopen', side_effect=HTTPError('url', 401, 'SECRET', {}, None)):
            with self.assertRaises(AIError) as error:
                AIClient({'AI_PROVIDER': 'ollama'}).complete([])
        self.assertNotIn('SECRET', str(error.exception))

    def test_openai_extracts_message_after_reasoning(self):
        payload = {'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [
            {'type': 'output_text', 'text': 'Ответ'}]}], 'status': 'completed'}
        with patch('ai_client.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            client = AIClient({'AI_PROVIDER': 'openai', 'AI_MODEL': 'test', 'OPENAI_API_KEY': 'fake'})
            self.assertEqual(client.complete([]), 'Ответ')


if __name__ == '__main__':
    unittest.main()
