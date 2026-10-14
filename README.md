# GensIA

Assistente pessoal modular, com prioridade ao processamento local e controlo
explícito sobre ferramentas e dados. Versão atual: **0.18.0** — protótipo em evolução.

## Começar

Requer Python 3.10 ou superior. Na pasta do repositório:

```powershell
py -3 -m gensia --help
py -3 -m gensia --version
py -3 -m unittest discover -s tests -v
```

A base por terminal usa a biblioteca padrão. As integrações de voz, PDF e API são
opcionais e têm instruções próprias no [guia de utilização](docs/USAGE.md).
Não é necessário instalar todas as bibliotecas para começar.

## Capacidades implementadas

| Área | Estado |
| --- | --- |
| Texto e modelos | Terminal e integração local com Ollama |
| Sistema | Listagem confinada e abertura explícita de aplicações permitidas |
| Memória | SQLite com guardar, consultar e apagar explícitos |
| Voz | Adaptadores Whisper/Piper e gravação limitada de microfone |
| Documentos | TXT/Markdown/PDF, pesquisa lexical e respostas com referências |
| Cibersegurança | URLs passivas, VirusTotal opt-in, CISA KEV e adaptador Bandit |
| API | Estado e diagnóstico read-only em loopback, com token |
| Interface gráfica | Planeada; ainda não implementada |

As capacidades opcionais precisam dos respetivos motores/modelos. Implementação
de um adaptador não significa validação com hardware ou serviços reais.

## Organização

- `gensia/`: módulos Python e interfaces CLI/API.
- `tests/`: testes automatizados.
- `docs/USAGE.md`: instalação opcional, comandos e exemplos.
- `docs/ARCHITECTURE.md`: arquitetura e limites de confiança.
- `PROGRESS.md`: histórico dos incrementos e próximo passo.
- `VALIDATION.txt`: evidências e limitações dos testes.
- `requirements-api.txt`: dependências opcionais da API.

## Validação

117 testes passaram no ambiente de desenvolvimento Linux/Python 3.12, com as
dependências opcionais da API instaladas. Sem estas dependências, seis testes HTTP
são omitidos explicitamente. Uma consulta HTTP real em loopback foi validada.
Windows, hardware de áudio e vários motores externos ainda precisam de testes reais.

## Privacidade e permissões

Não há fallback cloud automático. Consultas externas exigem autorização explícita.
Não envia emails. O modelo não recebe autorização para executar comandos livres.
A API não expõe memória, documentos nem operações mutáveis. Os adaptadores não
constituem uma sandbox de sistema operativo para código hostil.

Nunca versionar tokens, `.env`, gravações, documentos pessoais, bases SQLite,
pesos de modelos ou ambientes virtuais. Não foi atribuída uma licença de
distribuição ao projeto; as dependências mantêm as suas próprias licenças.

## Continuidade

Próximo incremento: painel local de leitura servido pela API, sem CDN e com token.
Consultar [PROGRESS.md](PROGRESS.md) antes de iniciar alterações.
