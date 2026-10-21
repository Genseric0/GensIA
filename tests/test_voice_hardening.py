from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from gensia.cli import main
from gensia.voice import MicrophoneRecorder, PiperSynthesizer, VoiceError, WhisperTranscriber


class VoiceHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.voice = self.root/'voice.onnx'
        self.voice.write_bytes(b'synthetic')
        Path(str(self.voice)+'.json').write_text('{}')
        self.audio = self.root/'audio.wav'
        self.audio.write_bytes(b'RIFF-synthetic')
        self.checkpoint = self.root/'weights.pt'
        self.checkpoint.write_bytes(b'synthetic, never loaded by a real engine')

    def test_truthy_approval_does_not_replace_piper_or_microphone_output(self):
        output = self.root/'out.wav'
        output.write_bytes(b'preserve')
        for approved in ('false', 'true', 1, [], {}, None):
            runner = Mock()
            with self.assertRaises(VoiceError):
                PiperSynthesizer(runner=runner).synthesize('synthetic',self.voice,output,approved)
            runner.assert_not_called()
            with patch('gensia.voice.importlib.import_module') as importer:
                with self.assertRaises(VoiceError):
                    MicrophoneRecorder().record(output,approve_overwrite=approved)
                importer.assert_not_called()
            self.assertEqual(output.read_bytes(),b'preserve')

    def test_piper_private_text_uses_stdin_and_reserved_file(self):
        def runner(command, **kwargs):
            self.assertNotIn('PRIVATE',repr(command))
            self.assertEqual(kwargs['input'],'PRIVATE Olá\n')
            self.assertEqual(kwargs['stdout'],subprocess.DEVNULL)
            self.assertEqual(kwargs['stderr'],subprocess.DEVNULL)
            self.assertIn('-I',command)
            temporary=Path(command[command.index('-f')+1])
            self.assertTrue(temporary.is_file())
            temporary.write_bytes(b'RIFF\x04\x00\x00\x00WAVEdata')
            return Mock(returncode=0)
        with patch.object(Path,'read_bytes',side_effect=AssertionError('unbounded WAV read')):
            result=PiperSynthesizer(runner=runner).synthesize('PRIVATE\nOlá',self.voice,self.root/'out.wav')
        self.assertTrue(result['local_invocation'])
        self.assertFalse(result['network_isolated'])
        self.assertNotIn('local_only',result)

    def test_piper_failure_does_not_echo_private_process_errors(self):
        for effect in (Mock(returncode=1,stderr='PRIVATE'),OSError('PRIVATE')):
            runner=Mock(side_effect=effect) if isinstance(effect,Exception) else Mock(return_value=effect)
            with self.assertRaises(VoiceError) as error:
                PiperSynthesizer(runner=runner).synthesize('synthetic',self.voice,self.root/'out.wav')
            self.assertNotIn('PRIVATE',str(error.exception))
            self.assertFalse((self.root/'out.wav').exists())

    def test_piper_refuses_late_existing_destination(self):
        output=self.root/'out.wav'
        def runner(command,**kwargs):
            Path(command[command.index('-f')+1]).write_bytes(b'RIFF\x04\x00\x00\x00WAVE')
            output.write_bytes(b'created by another writer')
            return Mock(returncode=0)
        with self.assertRaises(VoiceError):
            PiperSynthesizer(runner=runner).synthesize('synthetic',self.voice,output)
        self.assertEqual(output.read_bytes(),b'created by another writer')

    def test_whisper_missing_checkpoint_refuses_before_engine_import(self):
        with patch('gensia.voice.importlib.import_module') as importer:
            with self.assertRaisesRegex(VoiceError,'checkpoint'):
                WhisperTranscriber().transcribe(self.audio)
            importer.assert_not_called()

    def test_piper_oversized_wav_is_refused_before_header_read_or_publication(self):
        output = self.root/'out.wav'
        def runner(command, **kwargs):
            temporary = Path(command[command.index('-f')+1])
            with temporary.open('wb') as stream:
                stream.write(b'RIFF\x04\x00\x00\x00WAVE')
                stream.truncate(PiperSynthesizer.MAX_WAV_BYTES + 1)
            return Mock(returncode=0)
        with patch('gensia.voice.os.read') as read:
            with self.assertRaises(VoiceError):
                PiperSynthesizer(runner=runner).synthesize('synthetic', self.voice, output)
        read.assert_not_called()
        self.assertFalse(output.exists())

    def test_whisper_empty_directory_symlink_and_hardlink_checkpoints_refused(self):
        empty=self.root/'empty.pt';empty.touch()
        directory=self.root/'directory.pt';directory.mkdir()
        invalid=[empty,directory,self.root/'missing.pt']
        try:
            link=self.root/'link.pt';link.symlink_to(self.checkpoint);invalid.append(link)
            hard=self.root/'hard.pt';os.link(self.checkpoint,hard);invalid.append(hard)
        except OSError:
            pass
        for path in invalid:
            with patch('gensia.voice.importlib.import_module') as importer:
                with self.assertRaises(VoiceError):
                    WhisperTranscriber(checkpoint=path).transcribe(self.audio)
                importer.assert_not_called()

    def test_whisper_text_controls_types_and_unicode_refused(self):
        for text in ('PRIVATE\x1b]52;bad\x07','PRIVATE\ud800',{'text':'bad'},'x'*100001):
            model=Mock(transcribe=Mock(return_value={'text':text}))
            with patch('gensia.voice.importlib.import_module',return_value=Mock(load_model=Mock(return_value=model))):
                with self.assertRaises(VoiceError) as error:
                    WhisperTranscriber(checkpoint=self.checkpoint).transcribe(self.audio)
            self.assertNotIn('PRIVATE',str(error.exception))

    def test_whisper_engine_failure_is_fixed(self):
        with patch('gensia.voice.importlib.import_module',return_value=Mock(load_model=Mock(side_effect=RuntimeError('PRIVATE')))):
            with self.assertRaises(VoiceError) as error:
                WhisperTranscriber(checkpoint=self.checkpoint).transcribe(self.audio)
        self.assertNotIn('PRIVATE',str(error.exception))

    def test_stdin_is_bounded_and_strict(self):
        for raw in (b'\xff',b'PRIVATE\x1b',b'x'*20001):
            with self.assertRaises(VoiceError):
                PiperSynthesizer.read_stdin(BytesIO(raw))
        self.assertEqual(PiperSynthesizer.read_stdin(BytesIO('Olá 👋'.encode())), 'Olá 👋')

    def test_cli_missing_checkpoint_is_controlled(self):
        stdout,stderr=StringIO(),StringIO()
        with redirect_stdout(stdout),redirect_stderr(stderr):
            code=main(['voice','transcribe',str(self.audio)])
        self.assertEqual(code,7)
        self.assertEqual(stdout.getvalue(),'')
        self.assertIn('--checkpoint',stderr.getvalue())
