# Diagnóstico das proteções — v0.31.0

Na raiz do projeto, no mesmo Python usado pela GensIA:

```powershell
py -3 -m gensia.protections
```

Em Linux: `python -m gensia.protections`. Não precisa de Ollama, Bandit, pypdf,
FastAPI ou um token. Não instala nada, abre documentos pessoais, consulta notas,
inicia workers, envia pedidos de rede ou muda quotas. Imprime JSON; não guarda
relatório automaticamente. Saída 0 significa **relatório produzido**, não segurança
aprovada. Argumentos desconhecidos são recusados com saída 2.

## Campos e interpretação

| Campo | O que descreve | O que não comprova |
| --- | --- | --- |
| document_reads.mode=descriptor_relative | A via POSIX por descritores foi selecionada pelas capacidades do interpretador | Abertura bem-sucedida de um ficheiro concreto ou snapshot transacional |
| document_reads.mode=path_compatibility | Leitura limitada anterior, sem a proteção POSIX contra trocas concorrentes | Equivalência de segurança em Windows |
| resource_limits.state=available_unverified | Em Linux, símbolos/API e leitura das quotas herdadas disponíveis | Permissão para aplicar setrlimit ou aplicação efetiva no worker |
| resource_limits.state=unsupported | Backend de quotas não implementado nesta plataforma | Ausência de outros mecanismos do SO; não são utilizados pela GensIA |
| resource_limits.state=unavailable | Falha ao importar/consultar o backend Linux | Que o PDF funcionará apenas com timeout; o worker Linux pode recusar a execução |
| configured_caps / planned_caps | Tetos configurados e previsão com limites herdados menores | Quotas aplicadas ao processo atual, RAM livre ou orçamento global da máquina |

`execution_validated`, `enforcement_validated`, `limits_changed`, `os_sandbox` e
`commercial_approval` permanecem falsos. A previsão lê getrlimit, **não chama
setrlimit**. Se uma consulta falha, planned_caps fica null por inteiro; não publica
um relatório parcial nem o texto da exceção. Os tetos referem-se a espaço virtual,
CPU acumulada, tamanho por ficheiro escrito e core dump, não RAM reservada/disco
agregado. [Detalhes do worker](PDF_PROCESS.md) e [abertura de documentos](DOCUMENT_IO.md).

## Integração no doctor e API

`python -m gensia.doctor --model ETIQUETA` inclui o relatório em
`checks.document_protections`. O doctor continua a consultar GET /api/tags no
Ollama local. **Só o novo comando protections é completamente offline.**
preflight_passed mantém o significado anterior (Bandit encontrado/modelo listado),
mesmo que as proteções sejam limitadas; não é um indicador de segurança global.

A API existente inclui document_protections em `GET /diagnostics`, sem endpoint
novo nem execução de documentos. Mantém Bearer, Host exato, restrição de Origin,
apenas GET, ausência de query strings e no-store. O pedido HTTP é transporte do
relatório; network_requests=false descreve a própria inspeção de capacidades,
não nega a comunicação HTTP que o entregou. Não mostra tokens, caminhos pessoais,
conteúdo de documentos, lista de modelos, nomes de utilizador ou ambiente.

Na v0.32.0 existe um [painel experimental](PANEL.md). Só GET /diagnostics aceita
uma única Origin local exata, ainda com Bearer; outras origens continuam recusadas,
sem CORS. As três rotas públicas do painel servem apenas assets estáticos sem dados.

## Evidência de 16/10/2026

[Saída observada da CLI](validation/2026-10-16-protections.json): Linux,
descriptor_relative, linux_rlimit available_unverified. É o ambiente de validação,
não o computador do utilizador e não uma validação adicional de aplicação das quotas.

12 testes novos: nove do módulo, integração doctor, API em processo e API com
Uvicorn/HTTP real. Cobrem estados degradados, Windows/macOS simulados, limites
herdados menores, privacidade, ausência de efeitos laterais, CLI real e argumentos.
Consulta real de getrlimit manteve as quotas do pai inalteradas. Guardas de teste
recusaram abertura de ficheiros pessoais, rede, processos e aplicação de quotas.
Suite completa: 267 testes passaram, zero omitidos, incluindo os testes reais de
PDF/quotas anteriores e cinco testes de HTTP real. Bandit 1.9.4 nos três módulos
alterados: zero achados/erros. Sem Windows real, inferência nova ou aprovação comercial.

```bash
python -m unittest discover -s tests -p test_protections.py -v
```

Sem novas dependências. Referências primárias consultadas em 16/10/2026:
[Python 3.12 resource/getrlimit](https://docs.python.org/3.12/library/resource.html),
[capacidades dir_fd](https://docs.python.org/3.12/library/os.html#os.supports_dir_fd).
