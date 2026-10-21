# Instalação, build e validação contínua

Revisão de 21/10/2026. O código conserva Python e o núcleo sem dependências.
`pyproject.toml` acrescenta wheel instalável, comandos `gensia`/`gensia-api` e
extras opcionais API/PDF. Os assets HTML/CSS/JS acompanham o pacote. A licença
de distribuição do projeto continua por definir pelo titular; não foi atribuída
uma licença automaticamente.

## Instalação reproduzível no ambiente do projeto

PowerShell, na raiz do checkout:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[api,documents]' -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m gensia --help
$env:GENSIA_TEST_REAL_HTTP = '1'
$env:GENSIA_PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
.\.venv\Scripts\python.exe -m coverage run --branch --source=gensia -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m coverage report --show-missing
node --test tests/*.test.cjs
.\.venv\Scripts\python.exe -m build --wheel --no-isolation
.\.venv\Scripts\python.exe scripts/verify_installed.py dist
```

Linux: criar com `python3 -m venv .venv`, usar `.venv/bin/python` nos comandos
acima e `export GENSIA_TEST_REAL_HTTP=1 GENSIA_PYTHON="$PWD/.venv/bin/python"`.
O build sem isolamento exige os build tools pinados em requirements-dev.txt.
O verificador aceita um wheel ou uma pasta contendo exatamente um wheel; cria
uma venv nova, instala esse wheel sem rede/dependências e executa os comandos
de ajuda/versão, os seis assets de painel/conversa e um ciclo memória→backup→
restauro→consulta com dados sintéticos, a partir de outra pasta. Não inicia modelos,
abre aplicações ou instala os extras nesse ensaio mínimo.

Os pins diretos preservam FastAPI 0.143.0/Uvicorn 0.54.0/pypdf 6.20.1 já existentes.
Ferramentas de desenvolvimento verificadas no índice: pip 26.2.1, httpx 0.28.1,
Bandit 1.9.4, coverage 7.16.2, pip-audit 2.10.1, build 1.6.1,
setuptools 84.0.0 e wheel 0.48.0.
As dependências transitivas são resolvidas pelo pip; os pins diretos não constituem
um lock completo ou instalação offline. `pip check` e a auditoria verificam o
ambiente efetivamente resolvido. As versões/licenças observadas ficam em
`docs/DEPENDENCIES.md`.

O primeiro pip-audit nesta venv identificou 12 entradas de advisory em pip 25.0.1,
correspondentes a 6 IDs únicos; nenhum outro pacote instalado teve achados. pip foi
atualizado para 26.2.1 e pinado no ambiente de desenvolvimento. A versão foi
confirmada em [PyPI oficial](https://pypi.org/project/pip/26.2.1/) (MIT, Python >=3.10).
Isto corrige o instalador do ambiente de desenvolvimento; não implica que a GensIA
use pip durante a sua execução. O resultado final da auditoria fica no TEST_REPORT.

## Workflow

`.github/workflows/ci.yml` corre em pushes main/release, pull requests para main e
despacho manual. Matriz Linux/Windows com Python 3.12/3.13. Exige imports API/PDF
antes dos testes, ativa HTTP real em loopback com dados sintéticos, executa unittest,
coverage, contratos Node, build e instalação mínima do wheel.
Node 24 é configurado explicitamente por setup-node fixado por SHA.

O job `browser`, isolado em Ubuntu 24.04 com timeout de 20 minutos, instala
Playwright 1.62.1 e Chromium e executa:

```bash
NODE_PATH="$PWD/artifacts/browser/node_modules" GENSIA_PYTHON="$(python -c 'import sys; print(sys.executable)')" node scripts/validate_chat_browser.cjs --output artifacts/browser-evidence
```

O runner inicia a aplicação real em loopback, com um provider de resposta
explicitamente sintético. Verifica autenticação, contexto da conversa, renderização
de HTML como texto, cancelamento, nova conversa, limpeza de sessão e responsividade.
O job só passa com código 0. JSON e screenshots reais, quando produzidos, são
publicados como artifact, incluindo em falha. O diretório de evidência não deve
existir antes do runner. Estes testes não validam inferência com pesos reais.

Os skips específicos de POSIX/Linux podem ser legítimos no Windows; a sua presença
deve ser reportada no TEST_REPORT. A falta de FastAPI/Uvicorn/httpx/pypdf na matriz
faz o job falhar antes da suite e não é aceite como substituto dos testes API/PDF.
Coverage mede o processo principal; subprocessos não são automaticamente cobertos.
Não foi imposta percentagem arbitrária nem se considera coverage prova de qualidade.

O job security bloqueia achados Bandit médios/altos, sem respeitar supressões nosec,
e advisories encontrados pelo pip-audit. Indisponibilidade da consulta de advisories
ou pacote sem informação sob modo strict falha o job, não equivale a auditoria limpa.
Bandit LOW continua sujeito a revisão; o gate não significa ausência de falhas.

O scanner `scripts/check_secrets.py` procura apenas assinaturas delimitadas de
alguns fornecedores e cabeçalhos de chaves privadas nos ficheiros atuais de texto
do Git. Reporta caminho/linha/categoria, nunca o valor. Recusa arquivos demasiado
grandes ou não acessíveis em vez de declarar sucesso. Não verifica todo o histórico,
credenciais sem essas assinaturas, documentos binários ou todos os formatos de
segredos. Não equivale a Gitleaks, que não estava instalado nesta execução.

Todos os jobs têm timeout, token `contents:read`, checkout sem persistir credenciais
e actions fixadas por SHA. Não há `pull_request_target`, secrets de produção,
deployment ou agente com custo por execução. Dependabot propõe atualizações
semanais de pins Python e Actions, sujeitos aos mesmos testes e revisão humana.

SHAs conferidos em refs oficiais em 20–21/10/2026:

- checkout6.0.2: `de0fac2e4500dabe0009e67214ff5f5447ce83dd`
- setup-python6.1.0: `83679a892e2d95755f2dac6acb0bfd1e9ac5d548`
- setup-node6.0.0: `2028fbc5c25fe9cf00d9f06a71cc4710d4507903`
- upload-artifact6.0.0: `b7c566a772e6b6bfb58ed0dc250532a479d7789f`

Referências: [checkout](https://github.com/actions/checkout/releases/tag/v6.0.2),
[setup-python](https://github.com/actions/setup-python/releases/tag/v6.1.0),
[setup-node](https://github.com/actions/setup-node/releases/tag/v6.0.0),
[upload-artifact](https://github.com/actions/upload-artifact/releases/tag/v6.0.0).
Actions Node24 precisam de runner compatível; GitHub-hosted indicado nas matrizes.

## Limites de evidência

Definir o workflow não prova que foi executado no GitHub. Os resultados remotos
devem ser consultados por commit e registados pelo responsável da entrega. Este
workflow não mantém o computador ligado nem executa desenvolvimento recorrente;
não reativa a automação que o utilizador cancelou.

O runner visual existente precisa de Playwright e Chromium compatível. O ambiente
local tinha Playwright 1.62.1, mas o executável Chromium esperado estava ausente
e o download terminou com ZIP truncado. A tentativa ficou registada como bloqueada,
sem PNG, em `docs/screenshots/chat-browser-2026-10-21/validation.json`.
Nenhum screenshot pode ser atribuído a um navegador que não foi executado.
Os contratos Node não substituem E2E visual; a integração de browser é documentada
separadamente em INTERFACE.md.
## Correção da consulta de dependências no CI

O job de segurança inicial falhou porque `pip-audit --strict` procurou a própria
distribuição editable `gensia-local 0.61.0` no PyPI, onde não está publicada.
`--skip-editable` também falhou na reprodução desta instalação e não é utilizado.
O job confirma primeiro que a única distribuição editable é `gensia-local`; qualquer
editable adicional bloqueia a auditoria, impedindo que uma dependência de terceiros
seja omitida silenciosamente. Depois exporta todas as versões instaladas:

```bash
python -m pip freeze --all --exclude-editable > artifacts/audit-requirements.txt
python -m pip_audit --strict --disable-pip --no-deps -r artifacts/audit-requirements.txt --progress-spinner off --format json --output artifacts/dependencies.json
```

`freeze --all` inclui pip, setuptools e todas as transitivas instaladas. `--no-deps`
impede nova resolução, pois cada distribuição já consta do inventário. A GensIA
continua coberta pela revisão, Bandit e regressões. Não se ignora nenhum identificador
de vulnerabilidade; falhas de consulta continuam a bloquear o job. A validação local
deste comando não substitui a consulta do resultado remoto do commit corrigido.

O grupo de concorrência usa repositório de origem e branch: push e PR da mesma
branch cancelam trabalho duplicado. Branches homónimas de forks têm grupos
distintos. A alteração segue a [documentação de concorrência do GitHub](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
consultada em 21/10/2026. Não modifica permissões ou acesso a secrets.
