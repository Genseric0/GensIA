from concurrent.futures import ThreadPoolExecutor
import json
import threading
import unittest
from unittest.mock import Mock, patch

from gensia.chat import ChatError, conversation, checked_reply, prompt_for
from gensia.api import create_app, main
from gensia.providers import ProviderError


def payload(text='Olá', previous=None):
    return json.dumps({'messages': (previous or []) + [{'role':'user','content':text}]}, ensure_ascii=False).encode()


class ConversationTests(unittest.TestCase):
    def test_unicode_and_followup_keep_roles_and_context(self):
        previous = [{'role':'user','content':'DNS?'},{'role':'assistant','content':'Explicação 👋'}]
        messages = conversation(payload('E o cache?', previous))
        self.assertEqual(messages, previous + [{'role':'user','content':'E o cache?'}])
        self.assertIn('Não tens acesso a ferramentas', prompt_for(messages))

    def test_untrusted_json_duplicates_numbers_and_extra_fields_refused(self):
        for raw in (b'{"messages":[],"messages":[]}', b'{"messages":NaN}',
                    b'{"messages":1e999}', b'{"messages":[],"token":"PRIVATE"}',
                    b'{"messages":[{"role":"user","content":42}]}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ChatError):
                conversation(raw)

    def test_invalid_roles_sequence_or_controls_are_refused(self):
        for messages in ([], [{'role':'system','content':'do things'}],
                         [{'role':'assistant','content':'answer'}],
                         [{'role':'user','content':'q'},{'role':'assistant','content':'a'}],
                         [{'role':'user','content':'\x1b]52;PRIVATE\x07'}],
                         [{'role':'user','content':'\ud800'}]):
            with self.assertRaises(ChatError):
                conversation(json.dumps({'messages':messages}).encode())

    def test_sizes_are_bounded_and_assistant_reply_limits_allow_followup(self):
        with self.assertRaises(ChatError): conversation(payload('x'*4001))
        with self.assertRaises(ChatError): conversation(b' '*32769)
        for size in (4001, 8000):
            history = [{'role':'user','content':'q'}, {'role':'assistant','content':'a'*size}]
            self.assertEqual(len(conversation(payload('next', history))), 3)
        with self.assertRaises(ChatError):
            conversation(payload('next', [{'role':'user','content':'q'}, {'role':'assistant','content':'a'*8001}]))
        with self.assertRaises(ChatError):
            conversation(payload('x'*4000,[{'role':'user','content':'x'*4000}, {'role':'assistant','content':'x'*8000}]))

    def test_model_text_validation_is_explicit(self):
        self.assertEqual(checked_reply('Olá 👋\nTexto\tfinal'),'Olá 👋\nTexto\tfinal')
        for value in ('\x1b[31mPRIVATE', 'x'*8001, '\ud800', '', None):
            with self.assertRaises(ChatError): checked_reply(value)


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.token='a'*64
        self.provider=Mock()
        self.provider.ensure_local_model.return_value={'available':True,'locality':'confirmed_local'}
        self.provider.reply.return_value='Resposta sintética 👋'
        self.app=create_app(self.token,8765,chat_model='synthetic-local',provider=self.provider)
        self.client=TestClient(self.app,base_url='http://127.0.0.1:8765',headers={'Authorization':'Bearer '+self.token})
        self.addCleanup(self.client.close)

    def post(self, raw=None, **kwargs):
        return self.client.post('/chat',content=raw if raw is not None else payload(),
                                headers={'Content-Type':'application/json',**kwargs})

    def test_real_chat_route_passes_context_to_provider_without_actions(self):
        response=self.post(payload('DNS?', [{'role':'user','content':'ola'}, {'role':'assistant','content':'sim'}]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(), {'reply':'Resposta sintética 👋','actions_executed':False,'cloud_fallback':False})
        self.assertEqual(self.provider.reply.call_args.args[0], 'synthetic-local')
        self.assertIn('DNS?',self.provider.reply.call_args.args[1])

    def test_model_check_has_no_inference(self):
        response=self.client.get('/model')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['locality'],'confirmed_local')
        self.assertFalse(response.json()['inference_tested'])
        self.provider.reply.assert_not_called()

    def test_no_model_returns_setup_state_without_fake_reply(self):
        from fastapi.testclient import TestClient
        with TestClient(create_app(self.token),base_url='http://127.0.0.1:8765',headers={'Authorization':'Bearer '+self.token}) as client:
            self.assertFalse(client.get('/model').json()['configured'])
            self.assertEqual(client.post('/chat',json={'messages':[{'role':'user','content':'hello'}]}).status_code,503)

    def test_unauthorized_and_host_origin_guards_run_before_provider(self):
        for headers,code in (({'Authorization':''},401),({'Host':'evil.example'},400),
                             ({'Origin':'http://evil.example'},403),({'Sec-Fetch-Site':'cross-site'},403)):
            self.assertEqual(self.post(**headers).status_code,code)
        self.provider.reply.assert_not_called()
        self.assertEqual(self.post(Origin='http://127.0.0.1:8765').status_code,200)

    def test_duplicate_headers_query_and_cross_origin_preflight_refused(self):
        response=self.client.post('/chat',content=payload(),headers=[('Content-Type','application/json'),('Origin','http://127.0.0.1:8765'),('Origin','http://127.0.0.1:8765')])
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.post('/chat?token=PRIVATE',json={}).status_code,400)
        self.assertEqual(self.client.options('/chat',headers={'Origin':'https://evil.example'}).status_code,403)
        self.provider.reply.assert_not_called()

    def test_malformed_oversize_and_wrong_content_type_do_not_generate(self):
        self.assertEqual(self.post(b'{"messages":[],"messages":[]}').status_code,400)
        self.assertEqual(self.post(b'x'*32769).status_code,413)
        self.assertEqual(self.client.post('/chat',content=payload(),headers={'Content-Type':'text/plain'}).status_code,415)
        self.provider.reply.assert_not_called()

    def test_upstream_errors_are_fixed_without_private_content(self):
        self.provider.reply.side_effect=RuntimeError('PRIVATE')
        response=self.post()
        self.assertEqual(response.status_code,503)
        self.assertNotIn('PRIVATE',response.text)
        self.assertEqual(response.json()['error'],'generation_failed')

    def test_cloud_and_invalid_reply_are_refused(self):
        self.provider.reply.side_effect=ProviderError('cloud_model_blocked')
        self.assertEqual(self.post().json()['error'],'cloud_model_blocked')
        self.provider.reply.side_effect=None
        self.provider.reply.return_value='\x1b]52;PRIVATE\x07'
        response=self.post()
        self.assertEqual(response.status_code,502)
        self.assertNotIn('PRIVATE',response.text)

    def test_busy_worker_prevents_second_inference_and_model_query(self):
        entered,release=threading.Event(),threading.Event()
        def blocked(*args):
            entered.set()
            if not release.wait(5): raise RuntimeError('test deadline')
            return 'done'
        self.provider.reply.side_effect=blocked
        with ThreadPoolExecutor(max_workers=1) as executor:
            first=executor.submit(self.post)
            self.assertTrue(entered.wait(5))
            try:
                self.assertEqual(self.post().status_code,429)
                self.assertEqual(self.client.get('/model').status_code,429)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5).status_code,200)
        self.assertEqual(self.provider.reply.call_count,1)

    def test_public_shell_is_csp_protected_and_has_no_token(self):
        for path in ('/app','/app.css','/app.js'):
            response=self.client.get(path,headers={'Authorization':''})
            self.assertEqual(response.status_code,200)
            self.assertIn("default-src 'none'",response.headers['content-security-policy'])
            self.assertNotIn(self.token,response.text)
            self.assertNotIn('set-cookie',response.headers)

    def test_launcher_delegates_ephemeral_token_to_prebound_listener(self):
        with patch('gensia.api.run_local',return_value=0) as run:
            self.assertEqual(main(['--chat-model','synthetic-local','--ephemeral-token']),0)
        self.assertTrue(run.call_args.kwargs['display_token'])
        self.assertEqual(len(run.call_args.kwargs['token']),64)
