"""Transcrição local e explícita de ficheiros de áudio com Whisper."""
from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import os
import subprocess
import sys
import tempfile
import wave


class VoiceError(RuntimeError):
    """Erro previsível do módulo de voz."""


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

    def __init__(self, model: str = "base", device: str = "cpu", max_mib: int = 500):
        if model not in self.MODELS:
            raise ValueError(f"Modelo Whisper inválido: {model}")
        if device not in self.DEVICES:
            raise ValueError(f"Dispositivo Whisper inválido: {device}")
        if not 1 <= max_mib <= 2048:
            raise ValueError("--max-mib deve estar entre 1 e 2048")
        self.model = model
        self.device = device
        self.max_bytes = max_mib * 1024 * 1024

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
        language = language.strip().lower()
        if language == "auto":
            return None
        if not re.fullmatch(r"[a-z]{2,3}", language):
            raise VoiceError("Idioma inválido; usa um código como pt, en ou 'auto'.")
        return language

    def transcribe(self, audio_file: str | Path, language: str | None = "pt") -> Transcript:
        path = self._validate_file(audio_file)
        language = self._validate_language(language)
        try:
            whisper = importlib.import_module("whisper")
        except (ImportError, ModuleNotFoundError) as exc:
            raise VoiceError(
                "Whisper não está instalado. Instala 'openai-whisper' e o FFmpeg."
            ) from exc
        try:
            model = whisper.load_model(self.model, device=self.device)
            options = {"task": "transcribe", "fp16": self.device == "cuda"}
            if language is not None:
                options["language"] = language
            result = model.transcribe(str(path), **options)
        except VoiceError:
            raise
        except Exception as exc:
            raise VoiceError(f"A transcrição falhou: {exc}") from exc
        if not isinstance(result, dict):
            raise VoiceError("O Whisper devolveu uma resposta inválida.")
        text = str(result.get("text", "")).strip()
        if not text:
            raise VoiceError("O Whisper não encontrou fala no ficheiro.")
        detected = result.get("language")
        segments = result.get("segments")
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
        if output.exists() and not approve_overwrite:
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
        if len(text) > self.MAX_TEXT or "\x00" in text:
            raise VoiceError(f"Texto inválido ou acima de {self.MAX_TEXT} caracteres.")
        voice, _config = self._voice_files(voice_file)
        output = self._output_path(output_file, approve_overwrite)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}-", suffix=".wav", dir=output.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.unlink()
        command = [
            sys.executable,
            "-m",
            "piper",
            "-m",
            str(voice),
            "-f",
            str(temporary),
            "--",
            text.strip(),
        ]
        try:
            completed = self.runner(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or "erro não especificado").strip()[:500]
                raise VoiceError(f"O Piper falhou: {detail}")
            if not temporary.is_file():
                raise VoiceError("O Piper terminou sem criar o WAV.")
            header = temporary.read_bytes()[:12]
            if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                raise VoiceError("O Piper criou um ficheiro que não é WAV válido.")
            os.replace(temporary, output)
            return {
                "output": str(output),
                "bytes": output.stat().st_size,
                "voice": voice.name,
                "local_only": True,
            }
        except subprocess.TimeoutExpired as exc:
            raise VoiceError("O Piper excedeu o tempo limite.") from exc
        except OSError as exc:
            raise VoiceError(f"Não foi possível executar o Piper: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)


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
        if output.exists() and not approve_overwrite:
            raise VoiceError("O WAV já existe; usa --approve-overwrite para o substituir.")
        if output.exists() and not output.is_file():
            raise VoiceError("O destino existente não é um ficheiro.")
        return output

    def list_devices(self) -> list[dict]:
        sounddevice = self._sounddevice()
        try:
            devices = sounddevice.query_devices()
        except Exception as exc:
            raise VoiceError(f"Não foi possível consultar os dispositivos: {exc}") from exc
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
            os.replace(temporary, output)
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
        except Exception as exc:
            raise VoiceError(f"A gravação do microfone falhou: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)
