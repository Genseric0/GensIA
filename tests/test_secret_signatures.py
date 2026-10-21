import unittest

from scripts.check_secrets import findings


class SecretSignatureTests(unittest.TestCase):
    def test_provider_tokens_report_only_signature_and_line(self):
        token = b'ghp_' + b'A' * 36
        result = findings(b'first line\nvalue=' + token)
        self.assertEqual(result, [{'kind': 'github_classic_token', 'line': 2}])
        self.assertNotIn(token.decode(), str(result))

    def test_private_key_header_is_reported(self):
        value = b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----'
        self.assertEqual(findings(value)[0]['kind'], 'private_key_header')

    def test_short_placeholders_and_environment_references_are_not_tokens(self):
        self.assertEqual(findings(b'GENSIA_API_TOKEN=\nTOKEN_FROM_ENV\nghp_example'), [])

    def test_multiple_provider_signatures_are_distinguished(self):
        sample = (b'AKIA' + b'A'*16 + b'\n' + b'sk-proj-' + b'z'*50)
        self.assertEqual({x['kind'] for x in findings(sample)},
                         {'aws_access_key_id', 'openai_project_token'})
