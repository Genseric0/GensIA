# Validação reproduzível do painel — v0.33.0

Runner opcional de desenvolvimento: `scripts/validate_panel_browser.cjs`. Usa uma
API temporária própria e contexto de browser novo; não aceita URL de serviço
existente, token do utilizador ou perfil pessoal. Não instala pacotes/browsers e
não é necessário para usar a CLI. O fluxo completo ainda não foi executado aqui.

## Pré-requisitos e execução

Node >=20, Playwright resolúvel por `require('playwright')`, Chromium compatível já
instalado e Python com requirements-api.txt. Metadados do pacote de desenvolvimento
observado: Playwright 1.62.1, Apache-2.0, Node >=20; não se afirma ser a última
release. Nenhuma dependência nova de produção. Não precisa de Ollama ou dados reais.

Na raiz, PowerShell:

```powershell
$env:GENSIA_PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
node scripts/validate_panel_browser.cjs evidencias-painel-novas
```

Linux, com o ambiente virtual ativo:

```bash
GENSIA_PYTHON="$(command -v python)" node scripts/validate_panel_browser.cjs evidencias-painel-novas
```

Escolher um diretório novo: se existir, mesmo como symlink, recusa substituí-lo.
Não elimina evidências antigas. Não copiar caminhos deste ambiente para a tua máquina.
Códigos: 0=todos os critérios passaram; 2=pré-requisito bloqueado; 1=falha, limpeza
incompleta ou destino indisponível. Não há instalação automática via npx/download.

## Contrato do runner

- Confirma browser antes de iniciar a API; contexto não persistente, service workers
  bloqueados, sem downloads, traces ou HAR.
- Gera token aleatório de teste. O helper reserva socket 127.0.0.1:porta efémera
  antes de anunciar a porta; runner aguarda /health autenticado e recusa continuar
  se o filho terminar. Sem shell. Filho recebe ambiente reduzido, não credenciais
  existentes/PYTHONPATH. Token novo só no ambiente do filho e headers de teste.
- Verifica shell vazio, Enter para autenticar, atualização manual, limpeza, token
  incorreto, reload sem sessão e cookies/localStorage/sessionStorage vazios.
- Conta CSP violations e erros de página sem copiar mensagens. Rotas da página só
  permitem GET na origem efémera/caminhos previstos, sem query/fragmento e sem
  Authorization fora de /diagnostics. Isto não é firewall nem monitorização da
  rede de todo o processo Chromium; não prova ausência de tráfego do SO.
- Verifica CSS carregado, três cartões/quatro linhas e ausência de overflow do
  documento em 1440, 390 e 320 px. Não é auditoria completa de acessibilidade.
- Antes de cada captura, exige campo do token vazio, URL sem parâmetros e segredo
  ausente do texto da página. Guarda PNGs até 5 MiB, com criação exclusiva:
  panel-locked-1440.png e panel-auth-1440/390/320.png. Só metadados do ambiente
  de teste; rever visualmente antes de publicar, nunca usar documentos de clientes.
- Fecha browser e termina/recolhe o seu helper (SIGTERM, depois SIGKILL se preciso),
  não serviços do utilizador. Falha de limpeza impede passed. Não é sandbox ou
  garantia contra SO/processos locais hostis.

validation.json guarda etapas, métricas e nomes de imagens, não tokens, erros,
headers ou URLs. passed exige todos os critérios, quatro capturas, três larguras
e limpeza concluída. blocked/failed ou contadores zero não aprovam o browser.
Em falha podem existir capturas parciais: não apresentá-las como validação completa.

## Resultado de 16/10/2026

[Manifesto real](validation/panel-browser-v033/validation.json): **blocked**, em
browser_launch, browser_executable_missing. Playwright 1.62.1 encontrado; Chromium
ausente. browser_flow_started=false; checks, métricas e capturas vazios. Nenhum
helper arrancou nessa tentativa. Não se instalou browser nem se geraram screenshots.
**Fluxo/layout/CSP em navegador real continuam por validar.**

Separadamente, helper real iniciado, consultado e encerrado por Python e por Node;
dados exigem o token novo, não o imprimem e o filho não fica em execução. 277 testes
Python passaram, zero omitidos; 18 Node passaram, incluindo oito novos do runner.
Dez Node anteriores continuam com DOM/fetch simulados. Dois testes Python novos
cobrem configuração inválida e lifecycle real. Bandit 1.9.4 no helper: 35 LOC,
zero achados/erros; não analisa o JavaScript. Sem teste Windows/browser real.

```bash
GENSIA_PYTHON="$(command -v python)" node --test tests/panel.test.cjs tests/panel_browser_runner.test.cjs
GENSIA_TEST_REAL_HTTP=1 python -m unittest discover -s tests -v
```

Sem GENSIA_PYTHON, o lifecycle real Node é omitido; os restantes não precisam de
Playwright. Lifecycle Python requer POSIX/API instalada. Os contratos testados não
são apresentados como execução das etapas completas do runner.

Fontes primárias consultadas em 16/10/2026:
[BrowserContext](https://playwright.dev/docs/api/class-browsercontext),
[screenshots](https://playwright.dev/docs/screenshots),
[preparação manual de browsers](https://playwright.dev/docs/browsers).
Sem alegações de desempenho. Estado comercial em [PRODUCT_READINESS.md](PRODUCT_READINESS.md).
