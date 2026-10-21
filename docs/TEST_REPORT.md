# Testes — 21/10/2026 — v0.62.0

## Incremento de memória0.62

Onze regressões novas em test_memory_check.py. Suíte completa com extras e HTTP
real:377 testes Python aprovados,zero omitidos/falhas,21.272s. Coverage combinado
87% exibido:2818 statements,320 não executados,854 ramos,140 parciais. Bandit
sem médios/elevados;scanner limitado140 ficheiros/0 achados. O wheel0.62 passou
sete etapas isoladas, incluindo a CLI check na base restaurada.
Ver MEMORY_RECOVERY.md para corrupção real, WAL, limites e recuperação. Não se validou falha
de energia, disco cheio ou hardware do cliente. Os [checks do PR1](https://github.com/Genseric0/GensIA/pull/1/checks)
são a referência para o commit corrente; os resultados0.61 abaixo são históricos.

## Evidência anterior — v0.61.0

Estado: **RELEASE BLOCKED**. Resultados reais no ambiente Linux/Python3.12.14,
Node24.19.0, dependências isoladas em `.venv`; não são testes no PC do cliente.

## CI remoto confirmado

[Run39521033113](https://github.com/Genseric0/GensIA/actions/runs/39521033113),
commit `04a866059fd65c1d7079c14b20f41ac620c76e02`: estado final **success**,
seis jobs concluídos com sucesso. Logs efetivamente consultados em21/10/2026:

| Configuração | Python | Node | Pacote instalado |
| --- | --- | --- | --- |
| Ubuntu24.04 /3.12 |366 PASS,0 omitidos,23.848s |44 PASS,0 omitidos |6 etapas PASS |
| Ubuntu24.04 /3.13 |366 PASS,0 omitidos,15.732s |44 PASS,0 omitidos |6 etapas PASS |
| Windows2025 /3.12 |341 PASS,25 omitidos,27.071s |44 PASS,0 omitidos |6 etapas PASS |
| Windows2025 /3.13 |341 PASS,25 omitidos,23.643s |44 PASS,0 omitidos |6 etapas PASS |

Os jobs Chromium e security passaram. Scanner remoto:136 ficheiros/0 assinaturas;
pipcheck e advisories sem achados; Bandit sem médios/elevados. As omissões Windows
são testes condicionados a recursos POSIX/Linux: descritores relativos,
O_NOFOLLOW, FIFO, bits de modo e limites/sinais de processos Linux, entre outros.
Os controlos equivalentes Windows ainda exigem desenvolvimento/verificação.
Não se apagaram testes nem se adicionaram omissões para fazer esta matriz passar.

## Baseline e regressão

| Execução | Resultado |
| --- | --- |
| Baseline206f4d1, sem extras globais | Python250 aprovados/27 omitidos; Node33 aprovados/1 falha de dependência |
| Mesmo commit, worktree independente, extras instalados | Python277 aprovados/0 omitidos em11.376s; Node34 aprovados/0 omitidos |
| Versão corrigida, API/PDF/HTTP ativados | Python 366 aprovados/0 omitidos/0 falhas em 22.883s |
| Todos os contratos Node atuais | 44 aprovados/0 omitidos/0 falhas em 0.722s |
| Coverage Python, linhas e ramos combinados | 86% exibido; 2770 statements,321 não executados; 838 ramos,138 parciais |
| Wheel reconstruído e instalado fora do checkout | Seis etapas aprovadas; inclui assets e memória→backup→restauro |
| pip check / pip-audit strict | Ambos exit0; zero vulnerabilidades conhecidas |
| Bandit, ignorando supressões | Zero médios/elevados; quatro baixos de alta confiança revistos |
| Scanner limitado de assinaturas de segredos |136 ficheiros,zero achados; não analisa todo o histórico Git |

A primeira regressão integrada encontrou uma falha: importar `gensia.api`
carregava prematuramente `gensia.providers`, contrariando o contrato de importação
isolada. A importação foi movida para `create_app`; a repetição integral passou.
O aviso de depreciação Starlette/TestClient/httpx permanece e não foi suprimido.

## Comandos reproduzíveis

```bash
python -m pip install -e '.[api,documents]' -r requirements-dev.txt
GENSIA_TEST_REAL_HTTP=1 python -m coverage run --branch --source=gensia -m unittest discover -s tests -q
python -m coverage report --show-missing
GENSIA_PYTHON="$(python -c 'import sys; print(sys.executable)')" node --test tests/*.test.cjs
python -m pip check
python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
python -m pip freeze --all --exclude-editable > artifacts/audit-requirements.txt
python -m pip_audit --strict --disable-pip --no-deps -r artifacts/audit-requirements.txt --progress-spinner off
python -m bandit -r gensia --severity-level medium --confidence-level low --ignore-nosec
python scripts/check_secrets.py
python -m build --wheel --no-isolation
python scripts/verify_installed.py dist
```

Os testes incluem autorização negativa, controlos de terminal, JSON/Unicode,
links e limites de dados, rollback/concorrência SQLite, backup/restauro,
autenticação/Host/Origin HTTP e mensagens sintéticas em sockets reais.
`test_chat_http.py` verifica conversa Unicode e seguimento, rejeição sem token
antes de inferência e corpo chunked acima de32768bytes. Os testes Node executam
JS real com DOM simulado, incluindo cancelamento, respostas tardias, expiração,
XSS como texto e corte de contexto por caracteres/bytes. Não são um browser.

## O que ainda não está validado

O runner Playwright tentou iniciar Chromium e registou `chromium_unavailable`;
a instalação do browser falhou com ZIP truncado. Nenhum PNG foi produzido.
`docs/screenshots/chat-browser-2026-10-21/validation.json` preserva o bloqueio.
O CI inclui um job E2E com browser e dados explicitamente sintéticos. Só os seus
resultados efetivamente consultados podem fechar a validação visual.

Atualização remota: o job Chromium118961545502 no run39520092421 passou. O ZIP
foi descarregado, hash confirmado e as quatro capturas inspecionadas. Evidência
em `screenshots/ci-39520092421/`. Linux3.12 e3.13 também passaram. O primeiro
Windows3.13 registou6 falhas,13 erros de limpeza e25 omissões específicas de
plataforma; estão a ser corrigidos os destinos symlink, fecho de fixtures SQLite
e expectativas de caminhos canónicos. O primeiro job security falhou por tentar
auditar o próprio pacote não publicado no PyPI. A configuração está a ser
corrigida sem ignorar advisories de dependências. A repetição Linux passou com
366 testes, incluindo seis regressões novas: guardas de destino e fecho/rollback
de conexões. O pacote foi reconstruído e o verificador isolado voltou a passar.
Ver checklist para a repetição remota.

Na repetição do PR, run39520718320, Linux3.12/3.13, Chromium e security passaram.
Windows passou as correções de SQLite/symlink e revelou uma falha restante no
relatório estático: separadores `\\` em vez de `/` no JSON. O código de produção
agora usa `Path.as_posix()` nos rótulos relativos, preservando caminhos nativos
para subprocessos. Os dez testes do scanner passaram após a correção; a matriz
remota deve confirmar a repetição completa. As25 omissões Windows são testes
POSIX/Linux explicitamente condicionados, não testes removidos para obter aprovação.

## Medição controlada do transporte

Executado `ChatHttpTests.setUpClass()` com o mesmo servidor sintético, uma chamada
de aquecimento e50 chamadas sequenciais de chat por `case.request(body)`, medidas
com `time.perf_counter`. Mensagem fixa: "Explica DNS com um exemplo."; um cliente.
Resultado:50 HTTP200,zero falhas, p50 1.522ms, p95 empírico2.893ms, máximo32.191ms.
Foi usada a48.ª amostra ordenada como percentil95. Servidor encerrado com
`doClassCleanups()`. Esta medição avalia somente overhead local de HTTP/autenticação
e serialização com resposta sintética. Não mede inferência, carga concorrente,
capacidade de hardware ou SLA; não pode sustentar alegações comerciais de desempenho.

Não houve inferência com pesos Ollama, Whisper/Piper reais, microfone, uso
interativo de aplicações Windows, carga representativa de clientes ou avaliação de SLA. Os tempos
da suíte não são benchmark do modelo nem teste de carga. Os limites de memória,
latência e concorrência de produção continuam pendentes. Não foram executados
ZAP, CodeQL, Semgrep, Gitleaks, OSV-Scanner ou Trivy.

O wheel isolado valida o núcleo sem extras; API/PDF foram validados no ambiente
de desenvolvimento. O CI deve repetir os testes em cada plataforma suportada.
Ver `RELEASE_CHECKLIST.md` para o estado do GitHub e os bloqueios restantes.
