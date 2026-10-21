from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import Mock, patch

from gensia.voice import MicrophoneRecorder, PiperSynthesizer, VoiceError, WhisperTranscriber


def checkpoint(directory):
    path = Path(directory) / 'synthetic.pt'
    path.write_bytes(b'synthetic checkpoint, never executed')
    return path


class VoiceTests(unittest.TestCase):
    def test_missing_file_is_rejected_before_import(self):
        with patch("gensia.voice.importlib.import_module") as importer:
            with self.assertRaises(VoiceError):
                WhisperTranscriber().transcribe("nao-existe.wav")
        importer.assert_not_called()

    def test_unknown_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.txt"
            path.write_text("não é áudio", encoding="utf-8")
            with self.assertRaises(VoiceError):
                WhisperTranscriber().transcribe(path)

    def test_missing_optional_dependency_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.wav"
            path.write_bytes(b"RIFF")
            with patch("gensia.voice.importlib.import_module", side_effect=ModuleNotFoundError):
                with self.assertRaisesRegex(VoiceError, "openai-whisper"):
                    WhisperTranscriber(checkpoint=checkpoint(directory)).transcribe(path)

    def test_transcribes_with_official_python_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.WAV"
            original = b"RIFF-audio-de-teste"
            path.write_bytes(original)
            model = Mock()
            model.transcribe.return_value = {
                "text": "  Olá, mundo.  ",
                "language": "pt",
                "segments": [{}, {}],
            }
            whisper = Mock()
            whisper.load_model.return_value = model
            with patch("gensia.voice.importlib.import_module", return_value=whisper):
                local = checkpoint(directory)
                result = WhisperTranscriber("base", "cpu", checkpoint=local).transcribe(path, "pt")
            whisper.load_model.assert_called_once_with(str(local.resolve()), device="cpu")
            model.transcribe.assert_called_once_with(
                str(path.resolve()), task="transcribe", fp16=False, language="pt"
            )
            self.assertEqual(result.text, "Olá, mundo.")
            self.assertEqual(result.segments, 2)
            self.assertEqual(path.read_bytes(), original)

    def test_auto_language_omits_language_option(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.mp3"
            path.write_bytes(b"audio")
            model = Mock()
            model.transcribe.return_value = {"text": "hello", "language": "en"}
            whisper = Mock(load_model=Mock(return_value=model))
            with patch("gensia.voice.importlib.import_module", return_value=whisper):
                result = WhisperTranscriber(checkpoint=checkpoint(directory)).transcribe(path, "auto")
            self.assertNotIn("language", model.transcribe.call_args.kwargs)
            self.assertEqual(result.language, "en")

    def test_empty_transcript_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio.flac"
            path.write_bytes(b"audio")
            model = Mock(transcribe=Mock(return_value={"text": "  "}))
            whisper = Mock(load_model=Mock(return_value=model))
            with patch("gensia.voice.importlib.import_module", return_value=whisper):
                with self.assertRaisesRegex(VoiceError, "não encontrou fala"):
                    WhisperTranscriber(checkpoint=checkpoint(directory)).transcribe(path)

    def test_configuration_is_bounded(self):
        with self.assertRaises(ValueError):
            WhisperTranscriber("desconhecido")
        with self.assertRaises(ValueError):
            WhisperTranscriber(max_mib=0)


class PiperTests(unittest.TestCase):
    @staticmethod
    def voice_files(directory: str) -> Path:
        voice = Path(directory) / "pt_PT-teste-medium.onnx"
        voice.write_bytes(b"modelo")
        Path(str(voice) + ".json").write_text("{}", encoding="utf-8")
        return voice

    def test_requires_local_voice_and_config(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "voz.onnx"
            with self.assertRaisesRegex(VoiceError, "ficheiro .onnx"):
                PiperSynthesizer().synthesize("Olá", missing, Path(directory) / "out.wav")
            missing.write_bytes(b"modelo")
            with self.assertRaisesRegex(VoiceError, "configuração"):
                PiperSynthesizer().synthesize("Olá", missing, Path(directory) / "out.wav")

    def test_uses_argument_list_and_atomically_writes_wav(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            temporary = Path(command[command.index("-f") + 1])
            temporary.write_bytes(b"RIFF\x04\x00\x00\x00WAVEdata")
            return Mock(returncode=0, stderr="")

        with tempfile.TemporaryDirectory() as directory:
            voice = self.voice_files(directory)
            output = Path(directory) / "fala.wav"
            result = PiperSynthesizer(runner=runner).synthesize(
                "Olá; $(whoami)", voice, output
            )
            self.assertEqual(output.read_bytes()[:4], b"RIFF")
            self.assertEqual(result["output"], str(output.resolve()))
        command, options = calls[0]
        self.assertNotIn("Olá; $(whoami)", command)
        self.assertEqual(options['input'], "Olá; $(whoami)\n")
        self.assertIn("-I", command)
        self.assertFalse(options["shell"])

    def test_refuses_overwrite_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            voice = self.voice_files(directory)
            output = Path(directory) / "fala.wav"
            output.write_bytes(b"original")
            runner = Mock()
            with self.assertRaisesRegex(VoiceError, "approve-overwrite"):
                PiperSynthesizer(runner=runner).synthesize("Olá", voice, output)
            self.assertEqual(output.read_bytes(), b"original")
            runner.assert_not_called()

    def test_failed_synthesis_does_not_replace_existing_output(self):
        def runner(command, **kwargs):
            Path(command[command.index("-f") + 1]).write_bytes(b"parcial")
            return Mock(returncode=1, stderr="modelo incompatível")

        with tempfile.TemporaryDirectory() as directory:
            voice = self.voice_files(directory)
            output = Path(directory) / "fala.wav"
            output.write_bytes(b"original")
            with self.assertRaisesRegex(VoiceError, "O Piper falhou"):
                PiperSynthesizer(runner=runner).synthesize(
                    "Olá", voice, output, approve_overwrite=True
                )
            self.assertEqual(output.read_bytes(), b"original")

    def test_rejects_invalid_text_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            voice = self.voice_files(directory)
            with self.assertRaisesRegex(VoiceError, "vazio"):
                PiperSynthesizer().synthesize(" ", voice, Path(directory) / "out.wav")
            with self.assertRaisesRegex(VoiceError, ".wav"):
                PiperSynthesizer().synthesize("Olá", voice, Path(directory) / "out.mp3")


class MicrophoneTests(unittest.TestCase):
    class FakeStream:
        def __init__(self, overflow=False):
            self.overflow = overflow

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, frames):
            overflow, self.overflow = self.overflow, False
            return b"\x00\x00" * frames, overflow

    class FakeSoundDevice:
        def __init__(self, overflow=False):
            self.stream = MicrophoneTests.FakeStream(overflow)
            self.settings = None
            self.stream_options = None

        def check_input_settings(self, **kwargs):
            self.settings = kwargs

        def RawInputStream(self, **kwargs):
            self.stream_options = kwargs
            return self.stream

        def query_devices(self):
            return [
                {"name": "Microfone USB", "max_input_channels": 2, "default_samplerate": 48000},
                {"name": "Altifalantes", "max_input_channels": 0, "default_samplerate": 48000},
            ]

    def test_records_bounded_pcm_wav(self):
        fake = self.FakeSoundDevice()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "microfone.wav"
            with patch("gensia.voice.importlib.import_module", return_value=fake):
                result = MicrophoneRecorder().record(
                    output, duration=0.5, device=3, sample_rate=8000
                )
            with wave.open(str(output), "rb") as audio:
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getframerate(), 8000)
                self.assertEqual(audio.getnframes(), 4000)
            self.assertEqual(result["duration_seconds"], 0.5)
            self.assertEqual(fake.settings["device"], 3)

    def test_lists_only_input_devices(self):
        fake = self.FakeSoundDevice()
        with patch("gensia.voice.importlib.import_module", return_value=fake):
            devices = MicrophoneRecorder().list_devices()
        self.assertEqual(devices, [{
            "id": 0,
            "name": "Microfone USB",
            "input_channels": 2,
            "default_sample_rate": 48000,
        }])

    def test_missing_dependency_is_clear(self):
        with patch("gensia.voice.importlib.import_module", side_effect=ModuleNotFoundError):
            with self.assertRaisesRegex(VoiceError, "sounddevice"):
                MicrophoneRecorder().list_devices()

    def test_overflow_preserves_existing_output(self):
        fake = self.FakeSoundDevice(overflow=True)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "microfone.wav"
            output.write_bytes(b"original")
            with patch("gensia.voice.importlib.import_module", return_value=fake):
                with self.assertRaisesRegex(VoiceError, "perdeu amostras"):
                    MicrophoneRecorder().record(
                        output, duration=0.5, sample_rate=8000, approve_overwrite=True
                    )
            self.assertEqual(output.read_bytes(), b"original")

    def test_duration_is_limited_before_device_access(self):
        with patch("gensia.voice.importlib.import_module") as importer:
            with self.assertRaisesRegex(VoiceError, "60 segundos"):
                MicrophoneRecorder().record("audio.wav", duration=61)
        importer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
