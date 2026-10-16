# Progresso GensIA

## 16/10/2026 — expiração local da sessão do painel — v0.34.0

O painel limpa metadados/referência reutilizável ao token e aborta o pedido após
cinco minutos desde o início da última consulta manual. Atualizar dentro do prazo
renova-o; eventos de foco/visibilidade não renovam. Verifica prazo antes de refresh,
antes de renderizar e em focus/pageshow/visibilitychange. Timer com geração impede
callbacks antigos de limparem sessão nova. Date.now + performance.now cobrem recuo
civil com monotónico ativo e suspensão em que só o civil avança; não são relógio
independente do SO. Página congelada limpa quando JS retoma, não ao segundo exato.
Não revoga credencial da API, não afeta outras janelas nem garante zeroização de
referências internas de fetch/browser. Sem storage, polling ou novas rotas/dependências.

12 testes Node novos: fronteira de cinco minutos, renovação, refresh vencido,
três eventos de retoma, alterações dos relógios, timer antecipado, respostas
tardias, abort e callback de sessão antiga. 30 Node passaram sem omissões (22
DOM/VM + oito runner), incluindo helper HTTP real; não é execução de browser.
277 Python passaram sem omissões com API/PDF e GENSIA_TEST_REAL_HTTP=1.
Primeiro ensaio Node falhou no helper porque o interpretador do venv tinha link
ausente; tentativa de recriação produziu loop, corrigido no ambiente de testes
com link explícito para Python 3.12.14 existente. Pacotes preservados, sem downloads;
suite repetida passou. Não é alteração da configuração da aplicação ou do PC do utilizador.

Docs de relógio/timers MDN consultadas em 16/10/2026. Sem novo Bandit (incremento
de lógica JS), browser real, screenshot, inferência, Windows ou aprovação comercial.
Não repetir E2E bloqueado idêntico; executar quando Chromium estiver disponível.
Próximo módulo: rever rotação assistida do token local com revogação efetiva por
reinício do servidor, sem adicionar uma rota mutável não autorizada.

## 16/10/2026 — runner E2E do painel e controlo de evidências — v0.33.0

Novo validate_panel_browser.cjs + panel_test_server.py: browser novo não persistente,
token aleatório sem reutilizar credenciais, socket loopback efémero reservado,
health autenticado, ambiente filho reduzido, sem shell/downloads. Política de GET
da página na mesma origem, verificações de auth/teclado/limpeza/reload/storage/CSP,
layout 1440/390/320 e guardas antes de PNG (token vazio/ausente no texto/URL fixa).
Diretório e ficheiros novos exclusivos; manifestos sanitizados, estados passed/
blocked/failed, limpeza do próprio browser/helper e sem uso de serviço existente.
Fluxo completo ainda não executado: tentativa real Playwright 1.62.1 encontrou
Chromium ausente e parou em browser_launch, browser_flow_started=false, sem iniciar
helper ou gerar screenshots. Manifesto docs/validation/panel-browser-v033/validation.json.
277 testes Python passaram, zero omitidos, 10,666s; dois novos validam configuração
e API temporária real com autenticação/encerramento. 18 Node passaram, zero omitidos
com GENSIA_PYTHON, oito novos de contratos, bloqueio, preservação e lifecycle real.
Bandit 1.9.4 no helper Python: 35 LOC, zero achados/erros; não analisa JS.
Package local Playwright 1.62.1 Apache-2.0/Node>=20 e docs oficiais consultados;
nenhuma dependência nova de produção ou instalação. Não se afirma release mais recente.
Próximo: E2E real quando Chromium existir, sem repetir bloqueio idêntico; pode
avançar expiração local da sessão por inatividade. Sem aprovação comercial nova.

## 16/10/2026 — painel local experimental de diagnóstico — v0.32.0

Assets HTML/CSS/JS fixos em /panel, /panel.css e /panel.js, públicos só como shell
vazia; nenhum dado/token embutido. Dados de /diagnostics continuam com Bearer.
Exceção Origin só para GET /diagnostics com valor único local exato; sem CORS,
sem alargar /agents/report ou outras rotas. Sec-Fetch-Site se presente só permite
same-origin/none, sem duplicados. Host exato/GET/no-query/no-store mantidos.
CSP só script/style/connect self, favicon data:, sem inline/frame/form, CORP/COOP.
Token em memória JS, campo limpo, sem storage/cookie/URL. Fetch fixo, redirect error,
credentials omit, 5s/64KiB; atualização manual, limpeza/abort e geração impedem
resposta tardia de repor dados. textContent para metadados/warnings, sem innerHTML.
275 testes Python passaram (oito novos), zero omitidos, 11,120s, sete HTTP reais.
Dez testes Node/VM passaram, não são browser/layout/CSP reais. Bandit 1.9.4 nos
dois módulos Python: 142 LOC, zero achados/erros, não analisa JS/CSS.
Primeira suite detetou falha no teste antigo de timeout baseado em PID por ficheiro
e /proc. Agora captura Popen real, confirma SIGKILL e waitpid já recolhido; suite
completa repetida e passou. Sem alteração da implementação do timeout em produção.
Playwright existente tentou launch; Chromium ausente. Não se instalou browser,
não se geraram capturas nem se alega fluxo visual validado. Registo parcial JSON.
Próximo: validação de browser real, teclado, CSP/rede/storage e capturas sem tokens.

## 16/10/2026 — diagnóstico read-only das proteções — v0.31.0

Novo comando python -m gensia.protections, só biblioteca padrão: relatório JSON
do modo descriptor_relative/path_compatibility, backend Linux de quotas e tetos
configurados/previstos com limites herdados menores. Consulta getrlimit sem aplicar
setrlimit; não abre documentos, acede a notas, inicia processos ou usa rede.
Estados available_unverified/unsupported/unavailable, sem texto de exceções nem
relatórios de quotas parciais. execution_validated/enforcement_validated e aprovação
comercial são sempre falsos. Saída 0 significa produção do relatório, não segurança.
Doctor inclui checks.document_protections sem mudar o preflight Bandit/modelo;
GET /diagnostics inclui o mesmo relatório com guardas anteriores, sem endpoint novo.
12 testes novos (nove unitários/CLI, doctor, API e socket real); 267 passaram,
zero omitidos, 13,822s, Linux/Python 3.12, PDF/quotas e cinco testes HTTP reais.
Uma montagem de mocks no teste read-only foi corrigida (patch de importlib afetava
a resolução de outros patches); suite repetida integralmente, sem erro de produção.
Bandit 1.9.4 nos três módulos: 239 LOC, zero achados/erros. CLI real observou
descriptor_relative/linux_rlimit disponível não validado; amostra JSON guardada.
Sem dependências novas, Windows real, inferência nova, GUI ou instalação no PC.
Próximo: painel local read-only do diagnóstico, com autenticação e sem CORS amplo.

## 16/10/2026 — abertura POSIX de documentos por descritores — v0.30.0

Novo document_io.py: abre cada componente com dir_fd/O_DIRECTORY/O_NOFOLLOW,
confirma identidade inicial da pasta-base, valida ficheiro regular com nlink=1,
compara stat/fstat antes da leitura limitada e metadados depois. NONBLOCK evita
bloqueio em FIFO trocado após stat. ExitStack fecha descritores em todos os ramos.
TXT/Markdown e leitura interna de PDF usam o módulo onde suportado; em Windows
permanece a leitura limitada anterior, sem alegar proteção equivalente. Erros na
via POSIX não tentam fallback. Worker PDF recebe identidade inicial do pai e
recusa mudança da pasta-base antes da leitura, sem alterar quotas existentes.
14 testes novos de races determinísticos, âncora após rename, hard links, FIFO,
alteração in-place, crescimento, fecho de recursos e contrato da identidade PDF.
255 testes passaram, zero omitidos, 11,154s, Linux/Python 3.12, pypdf e HTTP reais.
Casos de worker/modelo relevantes usam mocks; não houve inferência Ollama nova.
Bandit 1.9.4 em document_io.py/documents.py/pdf_process.py: 470 LOC, um LOW B404,
zero MEDIUM/HIGH/erros. Sem scan global novo. Guias/readme/avaliação atualizados.
Limites: não é sandbox/snapshot transacional; timestamps dependem do filesystem,
inicialização exige ambiente confiável, Windows e outros POSIX reais não testados.
Próximo: diagnóstico local das proteções de documentos/quotas ativas no ambiente.

## 16/10/2026 — quotas do worker PDF e recuperação — v0.29.0

Novo pdf_limits.py, só biblioteca padrão: em Linux aplica e confirma soft/hard
RLIMIT_AS 512 MiB, RLIMIT_CPU 30s, RLIMIT_FSIZE 2 MiB por ficheiro e CORE=0 antes
do pedido/parser. Nunca eleva limites herdados menores. Falha Linux interrompe
antes da leitura; outras plataformas reportam applied=false e conservam timeout.
Worker devolve envelope com documento/relatório validado pelo pai, que só aceita
sucesso Linux com relatório completo. Auditoria interna fica temporária; pai
regista sucesso/erro/timeout sem sujeitar o log persistente à quota do filho.
Nove testes novos; 241 passaram sem omissões em Linux/Python 3.12, HTTP/pypdf reais.
Alocação de 1 GiB recusada, escrita limitada a 2 MiB, filho encerrado por CPU
(limite 1s apenas no teste); quotas do pai intactas. Após falha real de recursos,
novo pedido extraiu PDF real, mesmo com log persistente maior que 2 MiB.
Bandit 1.9.4 nos dois módulos: 139 LOC, um LOW B404, zero MEDIUM/HIGH/erros.
Não é sandbox, quota agregada de disco/RAM/processos, ensaio PDF-bomba ou Windows
real; sem inferência Ollama nova. Fontes Python 3.12 resource consultadas hoje.
Próximo: abertura de documentos robusta contra trocas concorrentes de caminhos.

## 16/10/2026 — supervisão nos pipelines PDF — v0.28.0

SupervisedPdfDocuments adapta o worker a PdfDocument e reutiliza resumo/perguntas
e validação de citações existentes. CLI pdf-read/pdf-summarize/pdf-ask passam pelo
adaptador; LocalDocumentSearch também, incluindo ask-search e StudyAgent. Opção
--pdf-timeout nos comandos document relevantes, 30s por PDF por omissão; tutor
mantém esse valor. Alias pdf-read-supervised preservado. Sem fallback direto.
SafePdfDocuments permanece primitiva interna/de baixo nível usada pelo worker,
não foi alterada para evitar recursão e manter testes unitários do parser.
Sete testes novos: encaminhamento/limites/metadados, resumo/citações, falha antes
do modelo, pesquisa mista com páginas/linhas, tutor, CLI com modelo simulado e
CLI de leitura/pesquisa com pypdf real. 232 passaram, zero omitidos, incluindo
testes anteriores de timeout real/HTTP real. Modelo real não foi usado.
Bandit 1.9.4 nos três módulos alterados: um LOW B404, zero MEDIUM/HIGH/erros.
Persistem ausência de quotas de RAM/disco, sandbox e teste Windows real.
Próximo: limites de recursos do worker e validação de recuperação de falhas.

## 16/10/2026 — extração PDF supervisionada opt-in — v0.27.0

Novo document pdf-read-supervised, com max_mib/max_pages e pdf-timeout 1–120s,
30s por omissão. Worker próprio em Python -I -B, shell=False, cwd temporário,
PYTHONPATH/PYTHONHOME removidos, stderr descartado, pedido JSON por stdin e saída
em ficheiro temporário lida com limite de 2 MiB. Reutiliza leitura confinada e
limitada existente. Valida schema/metadados de saída; erros sem conteúdo do parser.
subprocess.run mata e recolhe o filho direto em timeout. Não é sandbox do SO;
sem quota de RAM/disco/rede, sem garantia sobre processos descendentes. Outros
comandos PDF continuam no caminho anterior. Não se declara migração completa.
requirements-documents.txt fixa pypdf 6.20.1 (BSD-3-Clause, Python>=3.9; GensIA>=3.10),
metadados primários/release 12/10/2026 verificados e pacote instalado só no ambiente
de desenvolvimento. Nove testes novos; 225 passaram sem omissões, incluindo CLI
com PDF sintético e pypdf real, erro real e timeout real com filho recolhido.
Bandit 1.9.4 apenas novo módulo: um LOW B404, zero MEDIUM/HIGH e zero erros.
Próximo: propagar a supervisão para resumo/perguntas/pesquisa PDF, com compatibilidade.

## 16/10/2026 — restauro para DB nova — v0.26.0

memory --db NOVA restore --input BACKUP --approve valida UTF-8/JSON v1, campos
exatos, tipos, datas com timezone, limites 8 MiB/1000 notas, duplicados, números
não permitidos e surrogates isolados. Entrada regular sem symlink, leitura limitada.
Cria schema conhecido em diretório temporário privado, insere com parâmetros,
verifica integrity_check e fecha SQLite antes de copiar para descritor O_EXCL do
destino. Assim SQLite nunca abre um caminho de destino que possa ser substituído
entre reserva e ligação. Sem sobrescrever DB existente, sem criar pastas-pai.
Preserva valores/datas e origem; falha de escrita pode deixar uma DB nova incompleta.
Doze testes novos; 216 passaram sem omissões, incluindo roundtrip, SQL como dados,
CLI real e segunda tentativa recusada. Bandit 1.9.4 no módulo: zero achados/erros.
Sem encriptação, merge, autenticação do ficheiro ou migração. Windows real e crash
durante cópia continuam por testar. Próximo: extração PDF em processo com timeout.

## 16/10/2026 — backup explícito da memória — v0.25.0

memory backup --output cria exportação lógica JSON UTF-8 schema_version=1,
kind=gensia.memory_backup, exported_at e notas com key/value/updated_at. Um SELECT
numa ligação read-only, até 1000 notas; substrings limitam campos devolvidos a Python
e validação rejeita dados fora do contrato. Sem truncar notas para as aceitar.
Até 8 MiB serializados; sem criar destino em falhas de leitura/validação/limites.
Criação O_EXCL com modo 0600 POSIX, flush/fsync; sem substituir ficheiro ou symlink,
sem criar diretórios. Falha de escrita pode deixar um novo ficheiro incompleto.
Saída da CLI só mostra contagem, tamanho, SHA-256 e encrypted=false; não as notas.
Pattern *.memory-backup.json adicionado ao gitignore. Sem encriptação ou restauro.
Nove testes novos; 204 passaram sem omissões, incluindo HTTP real e CLI de backup.
SQLite WAL real com valores committed incluídos. Bandit 1.9.4 no novo módulo:
zero achados/erros. Nenhum novo teste Windows, GUI, modelo ou scan global.
Próximo: validar/importar este formato para DB nova, nunca substituir DB existente.

## 16/10/2026 — resolução explícita de aplicações Windows — v0.24.3

Calculator/Notepad resolvidos via GetSystemDirectoryW; Explorer via
GetSystemWindowsDirectoryW, usando ctypes da biblioteca padrão. Caminho absoluto
passado no argv e em executable; cwd é o diretório de sistema consultado.
Sem PATH, SystemRoot/WINDIR, associação de ficheiros, shell ou fallback por nome.
Confirmação e allowlist mantidas. Lookup inválido ou executável ausente gera erro.
Sete testes novos e adaptação do teste antigo de argumento explícito: 195 testes
passaram, zero omitidos, incluindo HTTP real. APIs/processos Windows simulados;
nenhuma aplicação aberta. Bandit 1.9.4 apenas em tools.py: um LOW B404, zero
MEDIUM/HIGH e zero erros. Não houve novo scan global.
Windows 32/64-bit, redirecionamento WOW64, wrappers modernos e interface real
ainda precisam de ensaio. Próximo: backup/restauro explícito da memória local.

## 16/10/2026 — leitura limitada durante I/O — v0.24.2

TXT/Markdown/PDF usam read(limite + 1) em contexto binário em vez de read_bytes
sem limite. Stat continua a recusar ficheiros já grandes; crescimento após stat
é detetado pelo byte extra, sem carregar todo o conteúdo novo. Limites de tamanho
recusam bool, float e string na API Python. Sem alteração dos comandos CLI.
Seis testes novos: crescimento TXT/PDF, tamanhos exatos/UTF-8/hash, PDF completo
no limite (parser simulado), tipos inválidos e encerramento em erro de leitura.
Antes da correção, quatro dos seis testes falhavam. Depois: 188 testes passaram,
zero omitidos, incluindo HTTP real. Bandit 1.9.4 no módulo documents.py: zero
achados, zero erros. Não houve nova análise de todos os módulos neste incremento.
Persistem riscos de troca concorrente de caminhos e custo descomprimido do parser
PDF. Windows, GUI e inferência Ollama continuam sem validação nova.
Próximo: rever resolução de executáveis Windows; depois isolamento e backup/restauro.

## 16/10/2026 — robustez de auditoria/Ollama — v0.24.1

Concluídas as regressões iniciadas na revisão para uso comercial. Auditoria recusa
symlink pendente, ficheiros não regulares e hard links adicionais; usa O_NOFOLLOW
e O_NONBLOCK onde disponíveis, valida fstat e encapsula falhas de I/O em ToolError.
Diretórios-pai continuam a precisar de confiança; Windows sem O_NOFOLLOW mantém
risco de troca concorrente do último componente. Não é isolamento entre clientes.
Ollama valida porta/caminho/controlo da URL, não lê corpos de erro HTTP, fecha a
resposta e não reflete erros remotos. Erros estruturados e HTTP truncado são
controlados. Erros em resposta JSON 200 também não expõem conteúdo.
Onze testes novos; 182 testes passaram, zero omitidos, incluindo HTTP real.
Bandit 1.9.4 real: três LOW B404, zero MEDIUM/HIGH, zero erros de análise.
docs/PRODUCT_READINESS.md documenta dados, modelo inicial local por utilizador,
bloqueios e critérios de piloto; não declara produto pronto para venda.
Sem inferência, Windows ou navegador novo. Próximo: leitura limitada de documentos
durante I/O e revisão da resolução de executáveis Windows, antes de piloto.

## 15/10/2026 — regressão HTTP real — produto mantém v0.24.0

Adicionados quatro testes opt-in em tests/test_api_socket.py. Uvicorn real numa
thread, socket reservado em 127.0.0.1 com porta efémera, token aleatório temporário,
cliente http.client sem proxy, encerramento verificado e timeouts limitados.
Validado HTML 200 idêntico ao gerador, attachment/no-store/CSP, 401 sem token e
Authorization duplicado, 400 Host errado/duplicado e query, 403 Origin, 405 POST,
404 rota de execução. 171 testes passaram com GENSIA_TEST_REAL_HTTP=1, sem omissões.
Não altera funcionalidades, dependências de produção ou regras de autenticação.
Sem navegador, inferência Ollama ou novo scan Bandit. Próximo: capturas e desenho
da autenticação do painel; não confundir testes HTTP com validação visual.

## 15/10/2026 — exportação HTML autenticada — v0.24.0

GET /agents/report reutiliza render_report e entrega attachment UTF-8. Mantém
Host, Bearer, GET-only, rejeição de Origin/query. CSP permite estilos inline apenas
no HTML 200; JSON e erros não recebem essa permissão. Referrer-Policy no-referrer.
Três testes HTTP novos; 167 testes Python passaram sem omissões num venv novo com
FastAPI 0.143.0, Uvicorn 0.54.0, Starlette 1.8.0, Pydantic 2.14.1 e httpx 0.28.1.
TestClient emitiu aviso de depreciação do backend httpx; não falhou. Nenhum teste
de socket Uvicorn ou navegador novo, nenhuma inferência ou scan Bandit neste passo.
Guia docs/API_REPORT.md. Não é GUI interativa nem permite executar agentes.
Próximo: concluir capturas e desenhar autenticação do painel sem token em URL/storage.

## 15/10/2026 — pesquisa explícita de memória — v0.23.0

MemoryStore.search e CLI memory search: substring literal nas chaves e valores,
sensível a maiúsculas/acentos, SQL parametrizado, ordenação por chave, paginação
(20 resultados por omissão, máximo 200). Não cria DB ausente nem altera notas.
A pesquisa mostra valores explicitamente; list continua a omiti-los. Nenhuma
integração automática no chat, rede, embeddings ou dependência adicional.
Sete testes novos (incluindo subprocesso CLI real). Suite Python: 164 descobertos,
155 passaram, nove HTTP omitidos. Quatro testes Node dos critérios visuais passaram.
Capturas HTML e inferência Ollama continuam pendentes; sem novo scan Bandit.
Próximo: concluir capturas quando houver Chromium e retomar painel read-only.

## 15/10/2026 — infraestrutura de validação visual (produto mantém v0.22.1)

Adicionado scripts/validate_catalog_visual.cjs: gera HTML da CLI, testa larguras
1440/390/320, quatro cartões, aviso de estado e ausência de overflow horizontal.
Contexto offline, pedidos intercetados e recusados, saída exclusiva em nova pasta,
capturas full-page e validation.json com estado explícito. Não instala dependências.
Quatro testes Node dos critérios passaram. A execução integrada falhou antes de
abrir página: Playwright 1.62.1 disponível, Chromium ausente. Tentativa separada
de download via npx (1.64.1) recebeu ZIP inválido e terminou com código 1.
Nenhuma captura HTML criada, nenhuma validação visual humana afirmada.
Próximo: executar o script com Chromium correspondente ao Playwright instalado,
inspecionar as três imagens e só então publicar a galeria HTML para recrutadores.

## 15/10/2026 — exportação segura — v0.22.1

catalog_report aceita --output com criação exclusiva e UTF-8, sem substituir
destinos existentes (incluindo ficheiros vazios e symlinks). Sem novas dependências.
Códigos 0 sucesso, 13 destino existente, 14 falha de escrita. Stdout preservado.
157 testes descobertos: 148 passaram, nove HTTP omitidos por dependências ausentes.
Cinco testes novos, incluindo CLI real que grava uma vez e recusa a segunda.
Falhas durante escrita podem deixar um novo ficheiro incompleto; documentado.
Nenhuma validação visual, inferência ou scan Bandit novo neste incremento.
Próximo: validar apresentação desktop/mobile e painel autenticado de leitura.

## 15/10/2026 — módulo 22 — v0.22.0

Relatório HTML offline em gensia/catalog_report.py, com catálogo de agentes,
dependências, limites e aviso explícito de estado não observado. Sem JavaScript,
rede, token, servidores ou novos pacotes. Conteúdo escapado e CSP restritiva.
CLI escreve no stdout; exportação e abertura documentadas em docs/CATALOG_REPORT.md.
152 testes passaram (quatro novos). Tentativa de inspeção com Playwright bloqueada
pela ausência do binário Chromium: aparência desktop/mobile ainda por validar.
Não altera a API nem inicia agentes. Inferência real continua pendente.
Próximo: validação visual e painel autenticado de leitura integrado com a API.

## Apresentação visual — 2026-10-14

Adicionada galeria ao README e docs/SHOWCASE.md para avaliação técnica por recrutadores.
Cinco imagens SVG renderizam saídas reais da CLI, acompanhadas de transcrições e
scripts/capture_showcase.py para reprodução. Dados sintéticos em pasta temporária.
As cinco execuções terminaram com código zero. Nenhuma funcionalidade de produto
foi alterada; a versão mantém-se 0.21.0. GUI continua planeada e inferência real pendente.

## 14/10/2026 — módulo 21 — v0.21.0

Catálogo declarativo em gensia/agent_catalog.py, partilhado por CLI e API.
GET /agents autenticado apresenta capacidades, dependências e limites dos quatro
agentes. Contrato tipado schema_version=1 filtra campos não declarados. Estado de
execução não observado; dependências não verificadas; nenhuma execução exposta.
API não importa ferramentas/executores para servir metadados; sem novas dependências.

148 testes passaram (sete novos). HTTP real em Uvicorn confirmou 200 com quatro
agentes, 401 sem token, 405 para POST e no-store. Servidor encerrado. Bandit real:
17 módulos, três LOW B404, zero MEDIUM/HIGH. Sem navegador ou inferência real nesta
etapa. Guia: docs/AGENT_CATALOG_API.md. Próximo: painel local de leitura na mesma
origem, mantendo autenticação e sem expor execução ou dados pessoais.

## 14/10/2026 — módulo 20 — v0.20.0

Acrescentado `python -m gensia.doctor --model ETIQUETA`: diagnóstico explícito dos
pré-requisitos antes dos agentes. Verifica metadados/módulo Bandit, GET local
/api/tags e etiqueta exata. Não instala, descarrega, inicia serviços, envia prompts
ou lê documentos. Erros e inventário completo de modelos não são publicados.
Exit codes 0/12/2; aprovação de pré-requisitos não afirma inferência validada.

141 testes passaram (dez novos). Teste HTTP real com resposta sintética verificou
um GET sem corpo. CLI real: Bandit disponível, Ollama inacessível, modelo não
verificado, saída 12. Scan Bandit real: 16 módulos, três LOW B404, sem MEDIUM/HIGH.
Não se repetiu nem contornou o download bloqueado. Sem dependências novas.
Guia e evidências: docs/DOCTOR.md. Próximo: inferência real quando houver pesos
locais; painel read-only pode avançar independentemente dessa disponibilidade.

## 14/10/2026 — validação real e transporte local — v0.19.1

Recuperada a versão 0.19.0 do GitHub como base autoritativa. Bandit 1.9.4 instalado
apenas no ambiente de desenvolvimento e executado realmente: 15 módulos, três
avisos LOW B404 após correção. Fixture sintética detectada como B602 HIGH, sem
execução do seu conteúdo e sem alteração dos bytes.

Corrigido transporte do Ollama: opener próprio sem proxies de ambiente, com
redirecionamentos HTTP recusados. 131 testes passaram; dois novos testes usam
servidores HTTP locais reais para 301/302/303/307/308 e proxy.

Ollama 0.40.4 arrancou realmente em CPU, cloud desativada; /api/version e /api/tags
responderam, modelo ausente gerou ProviderUnavailable. Download qwen2.5:0.5b
bloqueado por resolução DNS do destino de armazenamento no ambiente. Não houve
inferência real. Servidores encerrados. Nada instalado no computador do utilizador.
Evidências em docs/validation/2026-10-14-real-engines.json; roteiro reproduzível
em scripts/validate_agents_real.py. Próximo: executar esse roteiro com pesos locais.

## 14/10/2026 — módulo 19 — v0.19.0

Pedido do utilizador: colocar agentes de segurança e outros a trabalhar na GensIA.
Implementada equipa local com coordenador determinístico, segurança (URLs/Bandit),
revisor com evidências e Ollama opcional, e tutor documental com Ollama local.
CLI independente: `python -m gensia.agents list|audit|study`. Falhas isoladas,
resultados parciais, limites de tarefas/evidências e auditoria reutilizam os
módulos existentes. Nenhuma saída de modelo é executada, nenhum serviço permanente
é instalado e não há fallback cloud. Guia: docs/AGENT_TEAM.md.

129 testes passaram (12 novos); CLI passiva executada realmente. Bandit e Ollama
simulados nos testes, sem execução real desses motores. A publicação no GitHub
não significa agentes em execução no computador do utilizador.

## 14/10/2026 — organização para GitHub

Destino confirmado: Genseric0/GensIA, repositório público inicialmente vazio.
Preparada importação da versão 0.18.0, sem alteração de funcionalidades: README
de apresentação, guia detalhado em docs/USAGE.md, código, testes, arquitetura e
histórico. Não foram incluídos ambientes, caches, ZIPs ou dados pessoais.
O painel gráfico continua por implementar. A publicação é verificável no histórico
Git; não reconstruímos commits históricos de desenvolvimento a partir dos ZIPs.

## 14/10/2026 — módulo 18 — v0.18.0

API FastAPI opcional com lançador python -m gensia.api, bind fixo 127.0.0.1,
porta 8765 configurável, token alfanumérico >=32 caracteres em variável de ambiente.
GET /health, /status e /diagnostics; dados permitidos explicitamente, sem acesso a
modelos, memória, documentos ou ferramentas. Host estrito, Origin recusado,
sem CORS/docs/CDN, sem query strings, apenas GET, no-store, access log desligado,
proxy headers desligados e concorrência limitada a 16. Não há ações mutáveis.

117 testes passaram com FastAPI/Uvicorn reais num venv de teste. HTTP real em
loopback devolveu status 200 e v0.18.0, processo encerrado no fim. pip check e
compileall passaram. Windows e navegador real não testados. TestClient emite aviso
de depreciação do httpx; migrar testes para httpx2 quando compatibilidade verificada.

Fontes consultadas em 14/10/2026: https://pypi.org/project/fastapi/ (0.143.0,
08/10/2026, MIT, Python >=3.10), https://pypi.org/project/uvicorn/ (0.54.0,
25/09/2026, BSD-3-Clause, Python >=3.10), https://uvicorn.dev/settings/ e
https://fastapi.tiangolo.com/tutorial/testing/ . Nenhum benchmark adotado.
Instalação restrita ao ambiente de teste, não ao computador do utilizador.

## 14/10/2026 — módulo 17 — v0.17.0

Priorizada correção de isolamento antes da API: executar python -m bandit com cwd
na pasta-base permitia shadowing por bandit.py local. Agora usa -I -B e cwd privado,
INI/YAML controlados, --ignore-nosec e stderr descartado (sem buffer ilimitado).
Não foram adotadas novas dependências. Bandit continua opcional, versão 1.9.4.
Campos network_accessed/files_modified passaram de false para null: não existe
monitorização nem sandbox do SO. Plugins instalados continuam dentro da confiança.

110 testes passaram. Novo teste executa Python real com flags isoladas, cwd hostil
e PYTHONPATH hostil, confirmando que o módulo local não é escolhido. Outro verifica
configuração explícita e cwd privado. Motor Bandit real e Windows não testados.
Fontes oficiais consultadas em 14/10/2026:
https://docs.python.org/3/using/cmdline.html (-I)
https://bandit.readthedocs.io/en/latest/config.html (.bandit e nosec)
https://bandit.readthedocs.io/en/latest/man/bandit.html (--ini e --ignore-nosec)

Limitações restantes: corrida entre preflight e leitura pelo motor; sem quota de
disco do relatório durante o processo; exclusões do Bandit usam padrões. Para
código deliberadamente hostil é necessário isolamento de SO. API continua na fila.

## 14/10/2026 — módulo 16 — v0.16.0

Análise estática local e explícita de Python com Bandit opcional. O comando
`security bandit` restringe o alvo a uma pasta-base, aceita diretório ou `.py`,
recusa travessia/symlinks, pré-valida quantidade e bytes e executa o motor sem
shell. O relatório JSON temporário é limitado, normalizado e não devolve código.

Incluídos thresholds de severidade/confiança, timeout, diretórios gerados excluídos,
remoção de `PYTHONPATH/PYTHONHOME`, sanitização de erros, limite de 500 resultados,
contagens agregadas, estado de completude e auditoria sem caminho em claro. A saída
declara que não houve rede ou modificação e que o resultado não prova segurança.

108 testes passaram, incluindo metacaracteres literais, confinamento, symlinks,
dependência ausente, timeout, falha do motor, relatório inválido/grande, exclusões,
truncamento e preservação do código. Bandit real não estava instalado; a interface
foi simulada. Referência validada: Bandit 1.9.4, Python >=3.10, Apache-2.0.

## 14/10/2026 — módulo 15 — v0.15.0

Catálogo CISA KEV com atualização externa explícita e consulta posterior local.
`kev-update` obtém somente o feed JSON oficial fixo após `--approve-external`,
valida integralmente o documento e grava-o de forma atómica. `kev-check` procura
um CVE no cache sem rede e devolve versão, data de publicação e SHA-256 utilizado.

Foram adicionados limites de 10 MiB, timeout, CVE normalizado, contagem consistente,
campos/datas válidos, deteção de duplicados, recusa de links simbólicos e preservação
do cache anterior. A saída explica que ausência do KEV não significa segurança e
que `dueDate` não é automaticamente um prazo legal fora do âmbito federal dos EUA.

100 testes passaram. Download, erros e cache foram simulados; nenhum pedido real à
CISA foi feito. A documentação oficial consultada em 14/10/2026 apresenta o KEV como
fonte autoritativa de vulnerabilidades exploradas no mundo real e disponibiliza
JSON, CSV e esquema.

## 14/10/2026 — módulo 14 — v0.14.0

Consulta externa de reputação de URL, opt-in, usando somente o endpoint de leitura
do VirusTotal API v3. Exige `--approve-external` e `VIRUSTOTAL_API_KEY`, usa GET por
HTTPS e nunca submete a URL para nova análise. O identificador é Base64 URL-safe
sem padding, conforme a documentação oficial.

URLs locais, privadas, com userinfo, hostname interno de uma etiqueta ou sufixo
local comum são recusadas antes da rede. A resposta é limitada a 1 MiB; erros não
expõem corpo remoto ou chave; auditoria guarda só impressão digital. Resultado 404
e ausência de deteções são descritos sem alegar segurança.

91 testes passaram. Rede e resposta foram simuladas, incluindo aprovação/chave
ausentes, endpoint/método/header, Base64, relatório, 404, resposta inválida/grande
e erros sanitizados. Não foi usada chave real nem contactado o VirusTotal.

## 14/10/2026 — módulo 13 — v0.13.0

Primeira capacidade de cibersegurança: análise sintática e passiva de URLs. Valida
HTTP/HTTPS, normaliza IDNA, identifica userinfo, HTTP sem TLS, IP literal/não público,
localhost, Punycode, portas não padrão e hostnames suspeitos. Não resolve DNS, abre
a URL ou envia informação externamente; o resultado nunca declara a URL segura.

83 testes passaram, incluindo IPv4/IPv6 locais, userinfo enganador, remoção de
credenciais da forma canónica, Punycode, porta inválida, esquemas perigosos, controlos
codificados, auditoria sem URL e integração CLI. Base técnica: RFC 3986 e OWASP SSRF
Prevention Cheat Sheet, consultados em 14/10/2026.

## 14/10/2026 — módulo 12 — v0.12.0

Resposta local fundamentada em vários documentos através de `ask-search`. Primeiro,
a pesquisa lexical seleciona até `top-k` trechos; apenas esses excertos, com caminho
e página/linhas, são enviados ao Ollama local. A saída deve citar `[fonte N]`, e
identificadores ausentes ou inválidos são sinalizados. Sem correspondência, o modelo
nem sequer é chamado.

77 testes passaram. Foi verificado que conteúdo irrelevante de outro ficheiro não
entra no prompt, além de citações válidas/ausentes/inválidas, ausência de resultados,
provider obrigatório antes da leitura e regressão completa. Ollama real não estava
disponível; a interface foi simulada e nenhum documento do utilizador foi usado.

## 13/10/2026 — módulo 11 — v0.11.0

Pesquisa lexical local e efémera em até dez documentos explicitamente indicados.
TXT/Markdown devolvem intervalos de linhas; PDF devolve página. A tokenização ignora
diferenças de maiúsculas e acentos, e o ranking TF-IDF usa apenas biblioteca padrão.
Não cria índice, não percorre pastas automaticamente e não contacta modelo ou rede.

73 testes passaram. Um caso misto real, com TXT e PDF criado localmente, colocou o
trecho PDF sobre NAT em primeiro lugar e devolveu a página 1. Foram testados ranking,
ausência de resultados, limites, confinamento da pasta e integração CLI. Nenhum
documento do utilizador foi acedido.

## 13/10/2026 — módulo 10 — v0.10.0

Perguntas locais sobre PDFs através de `pdf-ask`. Pergunta e texto extraído são
dados não confiáveis; a resposta deve usar `[p. N]` ou declarar que a informação
não foi encontrada. A GensIA recolhe citações, confirma se os números pertencem
ao PDF e sinaliza referências ausentes ou inválidas. Isto não valida semanticamente
a resposta: a página indicada ainda deve ser conferida.

67 testes passaram, cobrindo citações válidas, ausentes e fora do intervalo,
resposta “não encontrado”, limites da pergunta e regressão dos módulos anteriores.
Ollama real não estava disponível; respostas foram simuladas e nenhum documento
foi enviado a modelo ou serviço externo.

## 13/10/2026 — módulo 9 — v0.9.0

Extração local e explícita de texto incorporado em PDF com `pypdf`, confinamento
à pasta-base, limites de bytes/páginas/caracteres, bloqueio de PDFs encriptados e
erro quando OCR seria necessário. Leitura e resumo mantêm metadados, SHA-256,
marcadores de página e auditoria sem conteúdo. O resumo usa só o Ollama local e
trata o texto como dados não confiáveis.

62 testes passaram. Um PDF real criado localmente também foi extraído com pypdf
6.10.0 já presente neste ambiente. A referência verificada em 13/10/2026 é pypdf
6.20.1, BSD-3-Clause e Python >=3.9; nenhuma instalação foi alterada. Não foram
usados PDFs do utilizador, OCR, cloud ou Ollama real.

## 13/10/2026 — módulo 8 — v0.8.0

Leitura segura e explícita de TXT/Markdown local, com confinamento a pasta-base,
UTF-8, extensões permitidas, limites de tamanho, bloqueio de links/travessia e
impressão digital SHA-256. Resumo `study` ou `concise` usa apenas o provider
selecionado; atualmente, Ollama limitado a localhost. O documento é marcado como
dado não confiável e nunca é guardado na auditoria.

58 testes passaram. Foram testados caminhos absolutos e `..`, symlink, formato,
binário, UTF-8 inválido, tamanho, leitura CLI, provider ausente e prompt com uma
tentativa de injeção. Ollama real não estava disponível; nenhum documento foi
enviado a modelo real ou serviço externo.

## 13/10/2026 — módulo 7 — v0.7.0

Captura local explícita do microfone para WAV PCM int16 mono. Inclui listagem de
dispositivos de entrada, seleção por ID, duração entre 0,5 e 60 segundos, taxa de
8–48 kHz, deteção de overflow e escrita atómica. Não há escuta contínua,
transcrição automática, reprodução ou rede.

50 testes passaram. Foi criado e inspecionado um WAV real a partir de blocos PCM
simulados; foram testados limites, dependência ausente, filtragem de dispositivos,
overflow e preservação do destino anterior. Nenhum microfone físico foi acedido.
A dependência adotada é sounddevice 0.5.6 (17/08/2026), MIT, Python >=3.7,
multiplataforma e com wheels para Windows; a API RawInputStream dispensa NumPy.

## 13/10/2026 — módulo 6 — v0.6.0

Saída de voz local para WAV através da CLI oficial do Piper. A voz e configuração
devem existir localmente; não há download automático, reprodução ou fallback cloud.
Foram adicionados limite de texto, timeout, subprocesso sem shell, escrita atómica,
validação WAV e confirmação para substituir um destino existente.

44 testes passaram. O fluxo Piper foi testado com executor simulado, incluindo
argumentos literais, WAV válido, erro do motor e proteção do ficheiro anterior.
Piper e uma voz real não estão instalados neste ambiente; não foi gerado áudio real.
Fontes oficiais consultadas indicam Piper 1.8.0 (04/09/2026), Python >=3.9,
Windows x64, GPL-3.0-or-later e vozes pt_PT/pt_BR. Licenças das vozes variam.

## 13/10/2026 — módulo 5 — v0.5.0

Entrada de voz local por ficheiro: adaptador opcional para a API Python oficial do
OpenAI Whisper, comando `voice transcribe`, modelos/dispositivos permitidos, idioma
fixo ou automático, validação de extensão/tamanho e mensagens de erro próprias.
O áudio não é alterado nem persistido; não há microfone ou envio para cloud.

38 testes passaram. A integração do adaptador, opções, validações e ausência de
mutação do áudio foram testadas com a interface Whisper simulada. Whisper, FFmpeg,
pesos e áudio real não estavam disponíveis neste ambiente; por isso não se afirma
uma transcrição real nem instalação no computador do utilizador.

## 13/10/2026 — módulo 4 — v0.4.0

Memória SQLite explícita: set/get/list/delete, atualização por chave, paginação,
validação de tamanhos e SQL parametrizado. Base padrão na pasta pessoal, criada
apenas ao guardar. Nenhum acesso à memória pelo chat; não há encriptação.
31 testes passaram, incluindo persistência entre processos, eliminação seletiva,
texto SQL tratado como dados, base corrompida e ausência de acesso pelo chat.
Código executado em Linux/Python 3.12.14; Windows real ainda não validado.

## 13/10/2026 — módulo 3 — v0.3.0

Implementadas ferramentas explícitas para listar uma pasta autorizada e abrir três
aplicações permitidas no Windows. Incluídos confinamento por pasta-base, confirmação
`--approve`, execução sem shell, códigos de saída e auditoria sem caminhos.

Validação: 23 testes passaram. A listagem foi exercitada em diretórios temporários;
a abertura de aplicações foi validada com executor simulado. Nenhuma aplicação foi
aberta no computador do utilizador e nenhum Windows real foi usado nesta etapa.

## Histórico

- v0.2.0: integração Ollama local; 15 testes.
- v0.1.0: arquitetura e terminal; 9 testes.

## Retomar

1. Ler PROGRESS.md, README.md e VALIDATION.txt.
2. Executar runner de browser quando Chromium existir; não repetir bloqueio sem
   alteração do ambiente. Pode avançar expiração local da sessão do painel.
   Usar gensia.doctor
   para verificar o ambiente e concluir inferência real quando
   houver modelo Ollama instalado. Executar scripts/validate_agents_real.py.
   O painel read-only existe sem esse motor; manter token e sem CDN, Origin apenas
   na exceção local exata de GET /diagnostics. Não expor ações mutáveis.
3. Não guardar conversas automaticamente nem enviar memória ao modelo por padrão.
4. Atualizar documentação, testes e a mesma identidade do artefacto.

## Fila

- [x] Arquitetura e terminal.
- [x] Integração com modelo local.
- [x] Ferramentas do sistema, permissões e auditoria.
- [x] Memória persistente explícita (integração no chat pendente).
- [x] Voz inicial (ficheiro, microfone limitado e TTS; diálogo contínuo fica futuro).
- [x] Pesquisa, documentos e apoio ao estudo (base local com recuperação e citações).
- [x] Cibersegurança inicial (URL, reputação opt-in, CISA KEV e Bandit).
- [x] Coordenação inicial limitada de agentes especializados.
- [ ] Interface gráfica e orquestração avançada.
