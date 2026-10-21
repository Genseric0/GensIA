"""Transcrição local e explícita de ficheiros de áudio com Whisper."""
from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import os
import stat
import subprocess
import sys
import tempfile
import wave


class VoiceError(RuntimeError):
    """Erro previsível do módulo de voz."""


def _validate_text(text, maximum, message):
    if (not isinstance(text, str) or not text.strip() or len(text) > maximum
            or any((ord(char) < 32 and char not in '\t\n\r') or 127 <= ord(char) <= 159 for char in text)):
        raise VoiceError(message)
    try:
        text.encode('utf-8', errors='strict')
    except UnicodeError:
        raise VoiceError(message) from None
    return text.strip()


def _promote_audio(temporary, output, approve_overwrite):
    if approve_overwrite is True:
        os.replace(temporary, output)
    else:
        # Atomic exclusive publication: a late-created destination must survive.
        os.link(temporary, output)
        temporary.unlink()


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    segments: int
    model: str
    device: str

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "segments": self.segments,
            "model": self.model,
            "device": self.device,
        }


class WhisperTranscriber:
    """Adaptador pequeno para a API Python oficial do OpenAI Whisper.

    A dependência é importada apenas no momento da transcrição. Assim, instalar a
    GensIA base não instala modelos, não abre o microfone e não inicia rede.
    """

    MODELS = frozenset(("tiny", "base", "small", "medium", "large", "turbo"))
    DEVICES = frozenset(("cpu", "cuda"))
    EXTENSIONS = frozenset((".wav", ".mp3", ".flac", ".m4a", ".ogg", ".webm"))

    def __init__(self, model: str = "base", device: str = "cpu", max_mib: int = 500,
                 checkpoint: str | Path | None = None):
        if model not in self.MODELS:
            raise ValueError(f"Modelo Whisper inválido: {model}")
        if device not in self.DEVICES:
            raise ValueError(f"Dispositivo Whisper inválido: {device}")
        if not 1 <= max_mib <= 2048:
            raise ValueError("--max-mib deve estar entre 1 e 2048")
        self.model = model
        self.device = device
        self.max_bytes = max_mib * 1024 * 1024
        self.checkpoint = checkpoint

    def _checkpoint_path(self):
        if self.checkpoint is None:
            raise VoiceError('Fornece --checkpoint com um ficheiro .pt local confiável; não são descarregados modelos.')
        try:
            path = Path(self.checkpoint).expanduser()
            info = path.lstat()
            if (path.suffix.lower() != '.pt' or not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1 or not 1 <= info.st_size <= 4 * 1024**3
                    or getattr(info, 'st_file_attributes', 0) & 0x400):
                raise ValueError('invalid checkpoint')
            return path.resolve(strict=True)
        except (OSError, ValueError, TypeError):
            raise VoiceError('Checkpoint deve ser .pt local regular, sem links e até 4 GiB.') from None

    def _validate_file(self, audio_file: str | Path) -> Path:
        path = Path(audio_file).expanduser()
        if path.is_symlink():
            raise VoiceError("Links simbólicos de áudio não são aceites.")
        if not path.exists() or not path.is_file():
            raise VoiceError("O ficheiro de áudio não existe ou não é um ficheiro.")
        if path.suffix.lower() not in self.EXTENSIONS:
            allowed = ", ".join(sorted(self.EXTENSIONS))
            raise VoiceError(f"Formato de áudio não permitido. Usa: {allowed}.")
        if path.stat().st_size > self.max_bytes:
            raise VoiceError("O ficheiro de áudio excede o limite configurado.")
        return path.resolve()

    @staticmethod
    def _validate_language(language: str | None) -> str | None:
        if language is None:
            return None
        if not isinstance(language, str):
            raise VoiceError("Idioma inválido; usa um código como pt, en ou 'auto'.")
        language = language.strip().lower()
        if language == "auto":
            return None
        if not re.fullmatch(r"[a-z]{2,3}", language):
            raise VoiceError("Idioma inválido; usa um código como pt, en ou 'auto'.")
        return language

    def transcribe(self, audio_file: str | Path, language: str | None = "pt") -> Transcript:
        path = self._validate_file(audio_file)
        language = self._validate_language(language)
        checkpoint = self._checkpoint_path()
        try:
            whisper = importlib.import_module("whisper")
        except (ImportError, ModuleNotFoundError) as exc:
            raise VoiceError(
                "Whisper não está instalado. Instala 'openai-whisper' e o FFmpeg."
            ) from exc
        try:
            model = whisper.load_model(str(checkpoint), device=self.device)
            options = {"task": "transcribe", "fp16": self.device == "cuda"}
            if language is not None:
                options["language"] = language
            result = model.transcribe(str(path), **options)
        except VoiceError:
            raise
        except Exception:
            raise VoiceError("A transcrição falhou; verifica o áudio, checkpoint e dependências locais.") from None
        if not isinstance(result, dict):
            raise VoiceError("O Whisper devolveu uma resposta inválida.")
        text = result.get("text", "")
        if isinstance(text, str) and not text.strip():
            raise VoiceError("O Whisper não encontrou fala no ficheiro.")
        text = _validate_text(text, 100000, 'O Whisper devolveu texto inválido ou excessivo.')
        detected = result.get("language")
        segments = result.get("segments")
        if detected is not None and (not isinstance(detected, str) or not re.fullmatch(r'[a-z]{2,3}', detected)):
            raise VoiceError('O Whisper devolveu idioma inválido.')
        if segments is not None and (not isinstance(segments, list) or len(segments) > 100000):
            raise VoiceError('O Whisper devolveu segmentos inválidos.')
        return Transcript(
            text=text,
            language=str(detected) if detected else language,
            segments=len(segments) if isinstance(segments, list) else 0,
            model=self.model,
            device=self.device,
        )


class PiperSynthesizer:
    """Cria um WAV local através da CLI oficial do Piper, sem reprodução."""

    MAX_TEXT = 5000
    MAX_WAV_BYTES = 64 * 1024 * 1024

    def __init__(self, timeout: float = 120.0, runner=subprocess.run):
        if not 1 <= timeout <= 600:
            raise ValueError("--timeout deve estar entre 1 e 600 segundos")
        self.timeout = timeout
        self.runner = runner

    @staticmethod
    def _voice_files(voice_file: str | Path) -> tuple[Path, Path]:
        voice = Path(voice_file).expanduser()
        config = Path(str(voice) + ".json")
        if voice.is_symlink() or config.is_symlink():
            raise VoiceError("Links simbólicos de voz não são aceites.")
        if voice.suffix.lower() != ".onnx" or not voice.is_file():
            raise VoiceError("A voz deve ser um ficheiro .onnx local existente.")
        if not config.is_file():
            raise VoiceError("Falta o ficheiro de configuração .onnx.json da voz.")
        return voice.resolve(), config.resolve()

    @staticmethod
    def _output_path(output_file: str | Path, approve_overwrite: bool) -> Path:
        requested = Path(output_file).expanduser()
        if requested.suffix.lower() != ".wav":
            raise VoiceError("O destino deve terminar em .wav.")
        if requested.is_symlink():
            raise VoiceError("O destino não pode ser um link simbólico.")
        parent = requested.parent.resolve()
        if not parent.is_dir():
            raise VoiceError("A pasta de destino não existe.")
        output = parent / requested.name
        if output.exists() and approve_overwrite is not True:
            raise VoiceError("O WAV já existe; usa --approve-overwrite para o substituir.")
        if output.exists() and not output.is_file():
            raise VoiceError("O destino existente não é um ficheiro.")
        return output

    def synthesize(
        self,
        text: str,
        voice_file: str | Path,
        output_file: str | Path,
        approve_overwrite: bool = False,
    ) -> dict:
        if not isinstance(text, str) or not text.strip():
            raise VoiceError("O texto para síntese está vazio.")
        text = _validate_text(text, self.MAX_TEXT, f'Texto inválido ou acima de {self.MAX_TEXT} caracteres.')
        voice, _config = self._voice_files(voice_file)
        output = self._output_path(output_file, approve_overwrite)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}-", suffix=".wav", dir=output.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        command = [
            sys.executable,
            "-I",
            "-X", "utf8",
            "-m",
            "piper",
            "-m",
            str(voice),
            "-f",
            str(temporary),
        ]
        try:
            completed = self.runner(
                command,
                shell=False,
                input=' '.join(text.splitlines()) + '\n',
                encoding='utf-8',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=self.timeout,
            )
            if completed.returncode != 0:
                raise VoiceError("O Piper falhou; verifica a voz e as dependências locais.")
            info = temporary.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 12 <= info.st_size <= self.MAX_WAV_BYTES:
                raise VoiceError('O Piper criou uma saída inválida ou excessiva.')
            descriptor = os.open(temporary, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            try:
                opened = os.fstat(descriptor)
                if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                        or not 12 <= opened.st_size <= self.MAX_WAV_BYTES
                        or (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino)):
                    raise VoiceError('O Piper criou uma saída inválida ou alterada.')
                header = os.read(descriptor, 12)
            finally:
                os.close(descriptor)
            if len(header) != 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                raise VoiceError("O Piper criou um ficheiro que não é WAV válido.")
            _promote_audio(temporary, output, approve_overwrite)
            return {
                "output": str(output),
                "bytes": output.stat().st_size,
                "voice": voice.name,
                "local_invocation": True,
                "network_isolated": False,
                "text_transport": "stdin",
            }
        except subprocess.TimeoutExpired as exc:
            raise VoiceError("O Piper excedeu o tempo limite.") from exc
        except OSError:
            raise VoiceError("Não foi possível executar o Piper ou publicar o WAV; verifica as permissões e o destino.") from None
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def read_stdin(cls, stream):
        if stream.isatty():
            raise VoiceError('Redireciona um ficheiro UTF-8 para --stdin.')
        raw = stream.read(cls.MAX_TEXT * 4 + 1)
        if not isinstance(raw, bytes) or len(raw) > cls.MAX_TEXT * 4:
            raise VoiceError('Entrada UTF-8 inválida ou excessiva.')
        try:
            value = raw.decode('utf-8', errors='strict')
        except UnicodeError:
            raise VoiceError('Entrada UTF-8 inválida ou excessiva.') from None
        return _validate_text(value, cls.MAX_TEXT, 'Entrada UTF-8 inválida ou excessiva.')


class MicrophoneRecorder:
    """Grava uma janela curta do microfone para WAV PCM mono, apenas por ordem explícita."""

    MIN_DURATION = 0.5
    MAX_DURATION = 60.0
    MIN_SAMPLE_RATE = 8000
    MAX_SAMPLE_RATE = 48000

    @staticmethod
    def _sounddevice():
        try:
            return importlib.import_module("sounddevice")
        except (ImportError, ModuleNotFoundError) as exc:
            raise VoiceError(
                "Captura de microfone indisponível. Instala o pacote 'sounddevice'."
            ) from exc

    @staticmethod
    def _output_path(output_file: str | Path, approve_overwrite: bool) -> Path:
        requested = Path(output_file).expanduser()
        if requested.suffix.lower() != ".wav":
            raise VoiceError("O destino da gravação deve terminar em .wav.")
        if requested.is_symlink():
            raise VoiceError("O destino não pode ser um link simbólico.")
        parent = requested.parent.resolve()
        if not parent.is_dir():
            raise VoiceError("A pasta de destino não existe.")
        output = parent / requested.name
        if output.exists() and approve_overwrite is not True:
            raise VoiceError("O WAV já existe; usa --approve-overwrite para o substituir.")
        if output.exists() and not output.is_file():
            raise VoiceError("O destino existente não é um ficheiro.")
        return output

    def list_devices(self) -> list[dict]:
        sounddevice = self._sounddevice()
        try:
            devices = sounddevice.query_devices()
        except Exception:
            raise VoiceError("Não foi possível consultar os dispositivos locais.") from None
        result = []
        for index, device in enumerate(devices):
            inputs = int(device.get("max_input_channels", 0))
            if inputs > 0:
                result.append({
                    "id": index,
                    "name": str(device.get("name", ""))[:200],
                    "input_channels": inputs,
                    "default_sample_rate": int(float(device.get("default_samplerate", 0))),
                })
        return result

    def record(
        self,
        output_file: str | Path,
        duration: float = 5.0,
        device: int | None = None,
        sample_rate: int = 16000,
        approve_overwrite: bool = False,
    ) -> dict:
        if not self.MIN_DURATION <= duration <= self.MAX_DURATION:
            raise VoiceError("A duração deve estar entre 0,5 e 60 segundos.")
        if not self.MIN_SAMPLE_RATE <= sample_rate <= self.MAX_SAMPLE_RATE:
            raise VoiceError("A frequência deve estar entre 8000 e 48000 Hz.")
        if device is not None and device < 0:
            raise VoiceError("O identificador do microfone não pode ser negativo.")
        output = self._output_path(output_file, approve_overwrite)
        sounddevice = self._sounddevice()
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}-", suffix=".wav", dir=output.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        total_frames = int(round(duration * sample_rate))
        try:
            sounddevice.check_input_settings(
                device=device, channels=1, dtype="int16", samplerate=sample_rate
            )
            with wave.open(str(temporary), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(sample_rate)
                with sounddevice.RawInputStream(
                    samplerate=sample_rate,
                    blocksize=1024,
                    device=device,
                    channels=1,
                    dtype="int16",
                ) as stream:
                    remaining = total_frames
                    while remaining:
                        count = min(1024, remaining)
                        data, overflowed = stream.read(count)
                        if overflowed:
                            raise VoiceError("A gravação perdeu amostras; tenta novamente.")
                        payload = bytes(data)
                        if len(payload) != count * 2:
                            raise VoiceError("O dispositivo devolveu um bloco de áudio incompleto.")
                        audio.writeframesraw(payload)
                        remaining -= count
            _promote_audio(temporary, output, approve_overwrite)
            return {
                "output": str(output),
                "bytes": output.stat().st_size,
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "channels": 1,
                "device": device,
                "local_only": True,
            }
        except VoiceError:
            raise
        except Exception:
            raise VoiceError("A gravação do microfone falhou; verifica o dispositivo e as permissões.") from None
        finally:
            temporary.unlink(missing_ok=True)
