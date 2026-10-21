import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from gensia.providers import OllamaProvider, ProviderError


LOCAL = {'details': {'format': 'gguf'}, 'model_info': {'general.architecture': 'llama'}}


def response(document):
    raw = document if isinstance(document, bytes) else json.dumps(document).encode('utf-8')
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.read.return_value = raw
    return result


class ProviderHardeningTests(unittest.TestCase):
    def test_metadata_precedes_inference_and_contains_no_prompt(self):
        opened = Mock(side_effect=[response(LOCAL), response({'message': {'content': 'Olá 👋\ncode\tvalue'}})])
        with patch('gensia.providers._LOCAL_OPENER.open', opened):
            self.assertEqual(OllamaProvider('fixture').reply('PRIVATE prompt'), 'Olá 👋\ncode\tvalue')
        first, second = [call.args[0] for call in opened.call_args_list]
        self.assertTrue(first.full_url.endswith('/api/show'))
        self.assertEqual(json.loads(first.data), {'model': 'fixture'})
        self.assertNotIn(b'PRIVATE', first.data)
        self.assertTrue(second.full_url.endswith('/api/chat'))
        self.assertEqual(json.loads(second.data)['messages'][0]['content'], 'PRIVATE prompt')

    def test_cloud_name_blocked_without_transport(self):
        for model in ('fixture:cloud', 'fixture-cloud', 'FIXTURE:CLOUD'):
            with patch('gensia.providers._LOCAL_OPENER.open') as opened:
                with self.assertRaises(ProviderError) as error:
                    OllamaProvider(model).reply('synthetic')
            self.assertEqual(error.exception.code, 'cloud_model_blocked')
            opened.assert_not_called()

    def test_remote_metadata_never_sends_prompt(self):
        for field in ('remote_model', 'remote_host'):
            metadata = {**LOCAL, field: 'PRIVATE remote'}
            with patch('gensia.providers._LOCAL_OPENER.open', return_value=response(metadata)) as opened:
                with self.assertRaises(ProviderError) as error:
                    OllamaProvider('fixture').reply('PRIVATE prompt')
            self.assertEqual(error.exception.code, 'cloud_model_blocked')
            self.assertNotIn('PRIVATE', str(error.exception))
            self.assertEqual(opened.call_count, 1)

    def test_missing_malformed_and_unconfirmed_metadata_fail_closed(self):
        for metadata in ({}, {'details': {'format': 'gguf'}},
                         {'details': {'format': 'gguf'}, 'model_info': {}},
                         {'details': {'format': 'other'}, 'model_info': LOCAL['model_info']},
                         {**LOCAL, 'remote_host': False},
                         {'details': [], 'model_info': LOCAL['model_info']}):
            with patch('gensia.providers._LOCAL_OPENER.open', return_value=response(metadata)) as opened:
                with self.assertRaises(ProviderError):
                    OllamaProvider('fixture').reply('synthetic')
            self.assertEqual(opened.call_count, 1)

    def test_metadata_revalidated_each_request_no_positive_cache(self):
        opened = Mock(side_effect=[response(LOCAL), response({'message': {'content': 'local'}}),
                                  response({**LOCAL, 'remote_host': 'PRIVATE'})])
        with patch('gensia.providers._LOCAL_OPENER.open', opened):
            provider = OllamaProvider('fixture')
            self.assertEqual(provider.reply('first'), 'local')
            with self.assertRaises(ProviderError):
                provider.reply('second')
        self.assertEqual(opened.call_count, 3)

    def test_two_argument_api_does_not_mutate_shared_model(self):
        opened = Mock(side_effect=[response(LOCAL), response({'message': {'content': 'local'}})])
        provider = OllamaProvider('configured')
        with patch('gensia.providers._LOCAL_OPENER.open', opened):
            self.assertEqual(provider.reply('selected', 'synthetic'), 'local')
        self.assertEqual(provider.model, 'configured')
        self.assertTrue(all(json.loads(call.args[0].data)['model'] == 'selected'
                            for call in opened.call_args_list))

    def test_model_check_output_omits_metadata_paths_and_license(self):
        metadata = {**LOCAL, 'modelfile': 'PRIVATE', 'license': 'PRIVATE'}
        with patch('gensia.providers._LOCAL_OPENER.open', return_value=response(metadata)):
            result = OllamaProvider('fixture').ensure_local_model()
        self.assertEqual(result, {'available': True, 'locality': 'confirmed_local', 'inference_tested': False})
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_unsafe_or_invalid_input_rejected_before_metadata(self):
        for text in ('', '\x1b[2J', 'PRIVATE\ud800', 'x'*96001, None):
            with patch('gensia.providers._LOCAL_OPENER.open') as opened:
                with self.assertRaises(ProviderError):
                    OllamaProvider('fixture').reply(text)
            opened.assert_not_called()

    def test_terminal_controls_and_invalid_unicode_are_never_returned(self):
        for text in ('PRIVATE\x1b]52;c;YQ==\x07', 'PRIVATE\x00', 'PRIVATE\x9b31m', 'PRIVATE\ud800',
                     'approved\rPRIVATE'):
            opened = Mock(side_effect=[response(LOCAL), response({'message': {'content': text}})])
            with patch('gensia.providers._LOCAL_OPENER.open', opened):
                with self.assertRaises(ProviderError) as error:
                    OllamaProvider('fixture').reply('synthetic')
            self.assertEqual(error.exception.code, 'unsafe_text')
            self.assertNotIn('PRIVATE', str(error.exception))

    def test_windows_newlines_are_normalized_without_terminal_carriage_return(self):
        opened = Mock(side_effect=[response(LOCAL), response({'message': {'content': 'one\r\ntwo'}})])
        with patch('gensia.providers._LOCAL_OPENER.open', opened):
            self.assertEqual(OllamaProvider('fixture').reply('input\r\ntext'), 'one\ntwo')
        self.assertEqual(json.loads(opened.call_args_list[1].args[0].data)['messages'][0]['content'],
                         'input\ntext')

    def test_duplicate_keys_nonfinite_numbers_and_deep_json_refused(self):
        for raw in (b'{"details":{},"details":{}}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'{"x":1e999}', b'{"x":'+b'['*1500+b'0'+b']'*1500+b'}'):
            with patch('gensia.providers._LOCAL_OPENER.open', return_value=response(raw)):
                with self.assertRaises(ProviderError) as error:
                    OllamaProvider('fixture').ensure_local_model()
            self.assertEqual(error.exception.code, 'invalid_response')

    def test_remote_chat_or_invalid_role_done_refused(self):
        for document in ({'remote_host': 'PRIVATE', 'message': {'content': 'PRIVATE'}},
                         {'done': 'true', 'message': {'content': 'PRIVATE'}},
                         {'message': {'role': 'tool', 'content': 'PRIVATE'}}):
            opened = Mock(side_effect=[response(LOCAL), response(document)])
            with patch('gensia.providers._LOCAL_OPENER.open', opened):
                with self.assertRaises(ProviderError) as error:
                    OllamaProvider('fixture').reply('synthetic')
            self.assertNotIn('PRIVATE', str(error.exception))

    def test_http_error_has_fixed_code_and_body_is_closed_not_read(self):
        body = Mock(wraps=io.BytesIO(b'PRIVATE'))
        with patch('gensia.providers._LOCAL_OPENER.open', side_effect=HTTPError('http://127.0.0.1',404,'PRIVATE',{},body)):
            with self.assertRaises(ProviderError) as error:
                OllamaProvider('fixture').ensure_local_model()
        self.assertEqual(error.exception.code, 'model_not_found')
        body.read.assert_not_called()
        body.close.assert_called_once()
        self.assertNotIn('PRIVATE', str(error.exception))

    def test_invalid_timeout_and_model_cannot_reach_transport(self):
        for timeout in (True, float('nan'), float('inf'), -1, '1'):
            with self.assertRaises(ValueError):
                OllamaProvider('fixture', timeout=timeout)
        for model in ('PRIVATE\x1b[2J', 'PRIVATE\ud800', 'x'*201, []):
            with self.assertRaises(ValueError):
                OllamaProvider(model)
