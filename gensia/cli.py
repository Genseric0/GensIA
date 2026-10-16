"""Entrada por terminal; pode ligar apenas ao Ollama local."""
import argparse
import json
import os
import sys
from pathlib import Path
from .memory import MemoryStore, MemoryError
from .memory_backup import backup_notes
from .memory_restore import restore_notes
from .kev import CisaKevCatalog, KevError
from .documents import DocumentError, SafeTextDocuments
from .pdf_process import SupervisedPdfDocuments
from .search import LocalDocumentSearch
from .security import PassiveUrlAnalyzer, SecurityError, VirusTotalUrlReputation
from .static_analysis import BanditScanner, StaticAnalysisError
from . import __version__
from .core import Assistant
from .providers import OllamaProvider, ProviderUnavailable, UnconfiguredProvider
from .tools import AppLauncher, AuditLogger, SafeDirectoryTools, ToolError, ToolPermissionError
from .voice import MicrophoneRecorder, PiperSynthesizer, VoiceError, WhisperTranscriber


def _provider(args, parser):
    if args.provider == "none":
        return UnconfiguredProvider()
    needs_model = args.command in ("ask", "chat", None) or (
        args.command == "document" and args.document_command in ("summarize", "pdf-summarize", "pdf-ask", "ask-search")
    )
    if needs_model and not args.model:
        parser.error("--model é obrigatório quando --provider ollama é usado para conversar")
    try:
        return OllamaProvider(args.model, args.ollama_url, args.timeout)
    except ValueError as exc:
        parser.error(str(exc))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="gensia", description="GensIA — base local por terminal")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--provider", choices=("none", "ollama"), default="none")
    parser.add_argument("--model", help="nome exato de um modelo já instalado")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    sub = parser.add_subparsers(dest="command")
    memory = sub.add_parser("memory", help="guardar e consultar notas locais explícitas")
    memory.add_argument("--db", default=str(Path.home() / ".gensia" / "memory.sqlite3"))
    mem_sub = memory.add_subparsers(dest="memory_command", required=True)
    mem_set = mem_sub.add_parser("set", help="guardar ou substituir uma nota")
    mem_set.add_argument("key")
    mem_set.add_argument("value")
    mem_get = mem_sub.add_parser("get")
    mem_get.add_argument("key")
    mem_list = mem_sub.add_parser("list")
    mem_list.add_argument("--limit", type=int, default=50)
    mem_list.add_argument("--offset", type=int, default=0)
    mem_search = mem_sub.add_parser("search", help="pesquisa literal local; mostra valores das notas encontradas")
    mem_search.add_argument("query", help="texto exato, sensível a maiúsculas e acentos")
    mem_search.add_argument("--limit", type=int, default=20)
    mem_search.add_argument("--offset", type=int, default=0)
    mem_backup = mem_sub.add_parser("backup", help="exportar notas completas para um novo ficheiro JSON local")
    mem_backup.add_argument("--output", required=True, help="novo ficheiro; contém os valores das notas")
    mem_restore = mem_sub.add_parser("restore", help="restaurar backup validado para a base nova indicada por --db")
    mem_restore.add_argument("--input", required=True, help="backup JSON local")
    mem_restore.add_argument("--approve", action="store_true")
    mem_delete = mem_sub.add_parser("delete")
    mem_delete.add_argument("key")
    mem_delete.add_argument("--approve", action="store_true")
    sub.add_parser("chat", help="abrir sessão interativa")
    sub.add_parser("status", help="mostrar capacidades reais")
    sub.add_parser("doctor", help="diagnóstico local sem rede")
    voice = sub.add_parser("voice", help="transcrever áudio local explicitamente")
    voice_sub = voice.add_subparsers(dest="voice_command", required=True)
    transcribe = voice_sub.add_parser("transcribe", help="transcrever um ficheiro com Whisper")
    transcribe.add_argument("file")
    transcribe.add_argument("--model", dest="whisper_model", choices=tuple(sorted(WhisperTranscriber.MODELS)), default="base")
    transcribe.add_argument("--language", default="pt", help="código de idioma ou auto")
    transcribe.add_argument("--device", choices=tuple(sorted(WhisperTranscriber.DEVICES)), default="cpu")
    transcribe.add_argument("--max-mib", type=int, default=500)
    synthesize = voice_sub.add_parser("synthesize", help="criar um WAV local com Piper")
    synthesize.add_argument("text")
    synthesize.add_argument("--voice", required=True, help="ficheiro local VOZ.onnx")
    synthesize.add_argument("--output", required=True, help="ficheiro WAV de destino")
    synthesize.add_argument("--approve-overwrite", action="store_true")
    synthesize.add_argument("--tts-timeout", type=float, default=120.0)
    voice_sub.add_parser("devices", help="listar dispositivos locais com entrada de áudio")
    record = voice_sub.add_parser("record", help="gravar o microfone durante um período limitado")
    record.add_argument("--output", required=True, help="ficheiro WAV de destino")
    record.add_argument("--duration", type=float, default=5.0)
    record.add_argument("--device", type=int, help="ID devolvido por 'voice devices'")
    record.add_argument("--sample-rate", type=int, default=16000)
    record.add_argument("--approve-overwrite", action="store_true")
    document = sub.add_parser("document", help="ler ou resumir texto local explicitamente")
    document.add_argument("--workspace", required=True, help="pasta-base autorizada")
    document.add_argument("--audit", default=".gensia/audit.jsonl")
    document.add_argument("--max-kib", type=int, default=64)
    document_sub = document.add_subparsers(dest="document_command", required=True)
    doc_read = document_sub.add_parser("read", help="ler TXT/Markdown em UTF-8")
    doc_read.add_argument("path", help="caminho relativo à pasta-base")
    doc_summary = document_sub.add_parser("summarize", help="resumir com o provider escolhido")
    doc_summary.add_argument("path", help="caminho relativo à pasta-base")
    doc_summary.add_argument("--style", choices=("concise", "study"), default="study")
    pdf_read = document_sub.add_parser("pdf-read", help="extrair texto incorporado de PDF")
    pdf_read.add_argument("path", help="caminho relativo à pasta-base")
    pdf_read.add_argument("--max-mib", type=int, default=10)
    pdf_read.add_argument("--max-pages", type=int, default=25)
    pdf_supervised = document_sub.add_parser("pdf-read-supervised", help="extrair PDF num processo separado com timeout")
    pdf_supervised.add_argument("path")
    pdf_supervised.add_argument("--max-mib", type=int, default=10)
    pdf_supervised.add_argument("--max-pages", type=int, default=25)
    pdf_supervised.add_argument("--pdf-timeout", type=float, default=30.0)
    pdf_summary = document_sub.add_parser("pdf-summarize", help="resumir PDF com o provider escolhido")
    pdf_summary.add_argument("path", help="caminho relativo à pasta-base")
    pdf_summary.add_argument("--style", choices=("concise", "study"), default="study")
    pdf_summary.add_argument("--max-mib", type=int, default=10)
    pdf_summary.add_argument("--max-pages", type=int, default=25)
    pdf_ask = document_sub.add_parser("pdf-ask", help="perguntar sobre PDF com referências de página")
    pdf_ask.add_argument("path", help="caminho relativo à pasta-base")
    pdf_ask.add_argument("question", help="pergunta sobre o documento")
    pdf_ask.add_argument("--max-mib", type=int, default=10)
    pdf_ask.add_argument("--max-pages", type=int, default=25)
    doc_search = document_sub.add_parser("search", help="pesquisar localmente em vários documentos")
    doc_search.add_argument("query", help="termos de pesquisa")
    doc_search.add_argument("paths", nargs="+", help="1 a 10 caminhos relativos TXT/Markdown/PDF")
    doc_search.add_argument("--top-k", type=int, default=5)
    doc_search.add_argument("--max-mib", type=int, default=10)
    doc_search.add_argument("--max-pages", type=int, default=25)
    ask_search = document_sub.add_parser("ask-search", help="responder usando só trechos recuperados")
    ask_search.add_argument("question", help="pergunta sobre os documentos")
    ask_search.add_argument("paths", nargs="+", help="1 a 10 caminhos relativos TXT/Markdown/PDF")
    ask_search.add_argument("--top-k", type=int, default=5)
    ask_search.add_argument("--max-mib", type=int, default=10)
    ask_search.add_argument("--max-pages", type=int, default=25)
    for pdf_command in (pdf_read, pdf_summary, pdf_ask, doc_search, ask_search):
        pdf_command.add_argument("--pdf-timeout", type=float, default=30.0,
                                 help="prazo por PDF em segundos (1–120)")
    ask = sub.add_parser("ask", help="enviar uma pergunta ao motor de IA")
    ask.add_argument("text")
    tool = sub.add_parser("tool", help="executar ferramenta local explícita")
    tool.add_argument("--audit", default=".gensia/audit.jsonl")
    tool_sub = tool.add_subparsers(dest="tool_command", required=True)
    list_cmd = tool_sub.add_parser("list", help="listar uma pasta autorizada")
    list_cmd.add_argument("--workspace", required=True, help="pasta-base autorizada")
    list_cmd.add_argument("path", nargs="?", default=".", help="caminho relativo")
    list_cmd.add_argument("--limit", type=int, default=200)
    open_cmd = tool_sub.add_parser("open-app", help="abrir aplicação permitida no Windows")
    open_cmd.add_argument("app", choices=tuple(AppLauncher.WINDOWS_APPS))
    open_cmd.add_argument("--approve", action="store_true")
    security = sub.add_parser("security", help="análises locais e passivas")
    security.add_argument("--audit", default=".gensia/audit.jsonl")
    security_sub = security.add_subparsers(dest="security_command", required=True)
    security_url = security_sub.add_parser("url", help="analisar sintaxe de URL sem a abrir")
    security_url.add_argument("value")
    reputation = security_sub.add_parser(
        "url-reputation", help="consultar relatório existente no VirusTotal"
    )
    reputation.add_argument("value")
    reputation.add_argument("--approve-external", action="store_true")
    reputation.add_argument("--request-timeout", type=float, default=15.0)
    kev_update = security_sub.add_parser(
        "kev-update", help="atualizar explicitamente o cache oficial CISA KEV"
    )
    kev_update.add_argument(
        "--cache", default=str(Path.home() / ".gensia" / "cisa-kev.json")
    )
    kev_update.add_argument("--approve-external", action="store_true")
    kev_update.add_argument("--request-timeout", type=float, default=30.0)
    kev_check = security_sub.add_parser(
        "kev-check", help="consultar localmente uma CVE no cache CISA KEV"
    )
    kev_check.add_argument("cve_id")
    kev_check.add_argument(
        "--cache", default=str(Path.home() / ".gensia" / "cisa-kev.json")
    )
    bandit_scan = security_sub.add_parser(
        "bandit", help="analisar localmente um projeto Python sem o alterar"
    )
    bandit_scan.add_argument("--workspace", required=True, help="pasta-base autorizada")
    bandit_scan.add_argument("path", nargs="?", default=".", help="caminho relativo")
    bandit_scan.add_argument(
        "--severity", choices=("all", "low", "medium", "high"), default="low"
    )
    bandit_scan.add_argument(
        "--confidence", choices=("all", "low", "medium", "high"), default="low"
    )
    bandit_scan.add_argument("--scan-timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    if args.command == "security":
        try:
            audit = AuditLogger(args.audit)
            if args.security_command == "url":
                output = PassiveUrlAnalyzer(audit).analyze(args.value)
            elif args.security_command == "url-reputation":
                output = VirusTotalUrlReputation(
                    audit,
                    os.environ.get("VIRUSTOTAL_API_KEY", ""),
                    args.request_timeout,
                ).lookup(args.value, args.approve_external)
            elif args.security_command == "kev-update":
                output = CisaKevCatalog(audit).update(
                    args.cache, args.approve_external, args.request_timeout
                )
            elif args.security_command == "kev-check":
                output = CisaKevCatalog(audit).check(args.cve_id, args.cache)
            else:
                output = BanditScanner(args.workspace, audit).scan(
                    args.path, args.severity, args.confidence, args.scan_timeout
                )
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        except (SecurityError, KevError, StaticAnalysisError) as exc:
            print(str(exc), file=sys.stderr)
            return 9
    if args.command == "voice":
        try:
            if args.voice_command == "transcribe":
                engine = WhisperTranscriber(args.whisper_model, args.device, args.max_mib)
                output = engine.transcribe(args.file, args.language).as_dict()
            elif args.voice_command == "synthesize":
                engine = PiperSynthesizer(args.tts_timeout)
                output = engine.synthesize(
                    args.text, args.voice, args.output, args.approve_overwrite
                )
            elif args.voice_command == "devices":
                output = {"input_devices": MicrophoneRecorder().list_devices()}
            else:
                output = MicrophoneRecorder().record(
                    args.output,
                    args.duration,
                    args.device,
                    args.sample_rate,
                    args.approve_overwrite,
                )
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        except (VoiceError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 7
    if args.command == "memory":
        store = MemoryStore(args.db)
        try:
            if args.memory_command == "set":
                output = store.set(args.key, args.value)
            elif args.memory_command == "get":
                output = store.get(args.key)
            elif args.memory_command == "list":
                output = store.list(args.limit, args.offset)
            elif args.memory_command == "search":
                output = store.search(args.query, args.limit, args.offset)
            elif args.memory_command == "backup":
                output = backup_notes(store, args.output)
            elif args.memory_command == "restore":
                output = restore_notes(store, args.input, args.approve)
            else:
                output = store.delete(args.key, args.approve)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        except MemoryError as exc:
            print(str(exc), file=sys.stderr)
            return 6
    if args.command == "document":
        try:
            audit = AuditLogger(args.audit)
            reader = SafeTextDocuments(args.workspace, audit)
            if args.document_command == "read":
                output = reader.read(args.path, args.max_kib).as_dict()
            elif args.document_command == "pdf-read-supervised":
                from .pdf_process import extract_pdf_process
                output = extract_pdf_process(args.workspace, args.path, args.audit,
                                             args.max_mib, args.max_pages, args.pdf_timeout)
            elif args.document_command == "summarize":
                provider = _provider(args, parser)
                if isinstance(provider, UnconfiguredProvider):
                    raise ProviderUnavailable(
                        "Modelo não configurado. Usa --provider ollama --model NOME. "
                        "O documento não foi lido."
                    )
                output = reader.summarize(args.path, provider, args.style, args.max_kib)
            elif args.document_command in ("pdf-read", "pdf-summarize", "pdf-ask"):
                pdf = SupervisedPdfDocuments(args.workspace, audit, args.pdf_timeout)
                if args.document_command == "pdf-read":
                    output = pdf.read_pdf(args.path, args.max_mib, args.max_pages).as_dict()
                elif args.document_command == "pdf-summarize":
                    provider = _provider(args, parser)
                    if isinstance(provider, UnconfiguredProvider):
                        raise ProviderUnavailable(
                            "Modelo não configurado. Usa --provider ollama --model NOME. "
                            "O PDF não foi lido."
                        )
                    output = pdf.summarize_pdf(
                        args.path, provider, args.style, args.max_mib, args.max_pages
                    )
                else:
                    provider = _provider(args, parser)
                    if isinstance(provider, UnconfiguredProvider):
                        raise ProviderUnavailable(
                            "Modelo não configurado. Usa --provider ollama --model NOME. "
                            "O PDF não foi lido."
                        )
                    output = pdf.ask_pdf(
                        args.path, args.question, provider, args.max_mib, args.max_pages
                    )
            elif args.document_command == "search":
                output = LocalDocumentSearch(args.workspace, audit, args.pdf_timeout).search(
                    args.query, args.paths, args.top_k, args.max_kib,
                    args.max_mib, args.max_pages,
                )
            else:
                provider = _provider(args, parser)
                if isinstance(provider, UnconfiguredProvider):
                    raise ProviderUnavailable(
                        "Modelo não configurado. Usa --provider ollama --model NOME. "
                        "Os documentos não foram lidos."
                    )
                output = LocalDocumentSearch(args.workspace, audit, args.pdf_timeout).answer(
                    args.question, args.paths, provider, args.top_k, args.max_kib,
                    args.max_mib, args.max_pages,
                )
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        except ProviderUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 3
        except DocumentError as exc:
            print(str(exc), file=sys.stderr)
            return 8
    provider = _provider(args, parser)
    assistant = Assistant(provider)
    if args.command == "tool":
        audit = AuditLogger(args.audit)
        try:
            if args.tool_command == "list":
                output = SafeDirectoryTools(args.workspace, audit).list_directory(args.path, args.limit)
            else:
                output = AppLauncher(audit).open(args.app, args.approve)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        except ToolPermissionError as exc:
            print(str(exc), file=sys.stderr)
            return 4
        except ToolError as exc:
            print(str(exc), file=sys.stderr)
            return 5
    if args.command in ("status", "doctor"):
        data = assistant.status()
        if args.command == "doctor":
            data["python_supported"] = sys.version_info >= (3, 10)
            if isinstance(provider, OllamaProvider):
                try:
                    data["ollama_reachable"] = True
                    data["installed_models"] = provider.list_models()
                except ProviderUnavailable as exc:
                    data["ollama_reachable"] = False
                    data["ollama_error"] = str(exc)
            data["note"] = "Não verifica GPU ou microfone."
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if args.command == "ask":
        result = assistant.handle(args.text)
        print(result.text, file=sys.stdout if result.ok else sys.stderr)
        return result.code
    label = args.model if isinstance(provider, OllamaProvider) else "não configurado"
    print(f"GensIA {__version__} — /ajuda, /estado, /sair. Modelo: {label}.")
    while True:
        try:
            text = input("Tu> ")
        except (EOFError, KeyboardInterrupt):
            print("\nAté breve.")
            return 0
        if text.strip() == "/sair":
            print("Até breve.")
            return 0
        result = assistant.handle(text)
        print("GensIA> " + result.text)
