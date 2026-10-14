# Progresso GensIA

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
2. Validar equipa com Bandit/Ollama reais e projeto de exemplo. Depois criar painel
   local read-only na mesma origem, mantendo token e sem CDN; rever Origin apenas
   para a origem local exata. Não expor ações mutáveis.
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
