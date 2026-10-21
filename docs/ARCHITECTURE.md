# Arquitetura e decisões — 14/10/2026

## Estado da candidata0.61 — revisão20–21/10/2026

As secções abaixo preservam decisões históricas. O fluxo atual acrescenta /app
e POST/chat autenticado:browser → Host/Origin/Bearer → JSON/contextolimitado →
lockdeinferência → /api/show semprompt → /api/chat → respostavalidada →textContent.
O modelo nunca invoca ferramentas. Contexto fica na memória do browser;notas
persistentes continuam CLIexplícita. Consultar INTERFACE e SECURITY_AUDIT.

Abertura de apps:approvedisTrue →intentauditflush/fsync →spawnallowlist →auditfinal.
Intenção falhada bloqueia efeito;falha posterior não oculta abertura concluída.
SQLite:exclusivo0600,regular/linkúnico,transações,SQLparametrizado,projeçãoBLOB+
typeof+UTF8/tamanho/NUL/data. Backuppartilhavalidador;restoreexigebasenova/True.
Token é por processo,semcontas/RBAC;socket é reservado antes deexibir tokenoptin.
Lock limita concorrência,não quota temporal. Limites não constituem sandbox deSO.
Voz:Piperstdin/checkpointWhisperexplícito;hardwareaindanãocomprovado.

## Fluxos atuais

- Texto: CLI → Assistant → ModelProvider → resposta.
- Ferramenta: CLI → validação de política → execução direta → auditoria → resultado.
- Voz: CLI → validação do ficheiro → adaptador Whisper opcional → JSON.
- TTS: CLI → validação de texto/voz/destino → Piper local → WAV temporário → substituição atómica.
- Microfone: CLI → duração/dispositivo explícitos → RawInputStream → WAV temporário → substituição atómica.
- Documento: CLI → pasta-base/política → leitura UTF-8 → resposta direta ou prompt marcado → Ollama local.

Os dois fluxos estão separados. Uma resposta do modelo nunca se transforma
automaticamente em ação do sistema.

## Política das ferramentas

- `SafeDirectoryTools` exige uma pasta-base existente.
- Caminhos devem ser relativos e, após resolução, permanecer dentro da pasta-base.
- A listagem é rasa, limitada e não abre o conteúdo dos ficheiros.
- `AppLauncher` usa apenas `calculator`, `notepad` e `files` no Windows.
- Abrir aplicação exige `--approve`; não existe execução arbitrária.
- `subprocess.Popen` recebe lista de argumentos com `shell=False`.
- A auditoria regista apenas ação, resultado, data UTC e SHA-256 truncado do alvo.
- Um ficheiro de auditoria que seja link simbólico é recusado.

## Dependências

Somente biblioteca padrão Python. O Ollama continua opcional e local. Não foram
adicionados PyAutoGUI, Playwright ou framework multi-agente porque este módulo
não precisa deles.

`openai-whisper` é uma dependência opcional e importada apenas quando o comando de
voz é executado. O FFmpeg é um requisito externo do Whisper. A escolha inicial é a
API Python oficial, encapsulada em `WhisperTranscriber`, sem acoplar o núcleo ou o
provider Ollama. Modelo padrão: `base` em CPU; CUDA e modelos maiores exigem opção
explícita. O módulo nunca usa o microfone e não persiste áudio ou texto.

`piper-tts` também é opcional. A integração usa a CLI oficial através do mesmo
Python, com lista de argumentos e `shell=False`. Exige que o utilizador forneça uma
voz `.onnx` já descarregada e o respetivo `.onnx.json`; a GensIA não descarrega
vozes. O Piper atual é GPL-3.0-or-later, mas as vozes têm licenças independentes que
devem ser consultadas nos respetivos `MODEL_CARD`.

`sounddevice` é opcional e carregado apenas pelos comandos `voice devices` e
`voice record`. A captura usa `RawInputStream` com buffers Python, por isso não
adiciona NumPy. Grava PCM int16 mono por 0,5–60 segundos. O módulo valida o
dispositivo antes de abrir o stream e trata overflow como falha, sem promover o
WAV temporário. Não existe processo residente ou hotword.

## Documentos implementados (v0.8.0)

`SafeTextDocuments` aceita somente TXT/Markdown relativos a uma pasta-base. A
resolução rejeita travessia, caminhos absolutos, qualquer componente simbólico,
formatos não autorizados, NUL, codificação não UTF-8 e excesso de tamanho. A
leitura é explícita e não altera o documento.

O resumo usa o `ModelProvider` já existente. Nesta versão, a única implementação
configurável é o Ollama e o endpoint continua preso a loopback. O documento é
serializado como um campo JSON e precedido por instruções que o classificam como
dado não confiável. Isto é defesa em profundidade, não garantia contra prompt
injection. O hash SHA-256 devolvido permite identificar a versão resumida sem
guardar o conteúdo na auditoria.

## Memória implementada (v0.4.0)

CLI memory → MemoryStore → SQLite local. Nenhum import de MemoryStore no provider.
Usa biblioteca padrão, transações, parâmetros SQL e fecho explícito de ligações.
Listagens são paginadas; apenas get devolve o valor. O comando set é autorização
explícita para guardar/substituir a chave; delete exige --approve. Sem sincronização
ou encriptação. SQLite serve os dados estruturados desta etapa; pesquisa vetorial
com ChromaDB fica para uma necessidade posterior de recuperação semântica.

## Voz implementada (v0.5.0)

Transcrição de um ficheiro escolhido explicitamente, com formatos e tamanho
limitados, recusa de links simbólicos, idioma configurável e erros próprios. A
dependência não está instalada no ambiente de validação: a integração foi exercitada
contra uma implementação simulada da interface oficial. Áudio real fica para teste
no computador do utilizador.

## Síntese implementada (v0.6.0)

Texto explícito para WAV com Piper local. Há limite de tamanho, validação dos dois
ficheiros da voz, recusa de links simbólicos, timeout, verificação do cabeçalho WAV,
escrita temporária e confirmação para substituir ficheiro existente. Não há
reprodução automática, servidor HTTP ou fallback online.

## Microfone implementado (v0.7.0)

Listagem de entradas e gravação local por duração fixa. Taxa padrão de 16 kHz,
adequada ao próximo passo manual com Whisper. A escrita é atómica, substituir
requer confirmação e a captura não inicia transcrição nem qualquer ação externa.

## PDF implementado (v0.9.0)

`SafePdfDocuments` reutiliza o confinamento de `SafeTextDocuments` e carrega
`pypdf` apenas quando necessário. Valida caminho, extensão e tamanho antes do
parser; depois recusa encriptação, excesso de páginas/caracteres e ausência de
texto. Não executa OCR, não abre anexos e não usa rede. A extração ocorre no
processo principal, portanto os limites não equivalem a isolamento por sandbox.

## Perguntas com páginas (v0.10.0)

`pdf-ask` reutiliza a extração limitada de `SafePdfDocuments`. O prompt contém
pergunta e documento num objeto JSON e exige `[p. N]` por afirmação ou resposta
fixa de ausência. O pós-processamento aceita apenas números entre 1 e o total real
de páginas e expõe `present`, `missing`, `invalid` ou `not_applicable`. Isto valida
referências estruturalmente, não a relação semântica entre frase e página.

## Pesquisa lexical (v0.11.0)

`LocalDocumentSearch` recebe uma lista fechada de caminhos, reutiliza as políticas
de leitura existentes, divide TXT/Markdown por blocos com linhas e PDF por páginas,
normaliza Unicode e aplica um ranking TF-IDF em memória. Não existe descoberta de
ficheiros, índice persistente, embeddings ou provider. Assim, pesquisa não autoriza
leitura futura nem expande o conjunto selecionado.

## Resposta fundamentada (v0.12.0)

`LocalDocumentSearch.answer` executa retrieval antes da geração. Só os resultados
`top-k` são serializados como JSON para o provider, com IDs, caminhos e localização.
A saída é pós-processada para referências `[fonte N]`; IDs fora do conjunto são
marcados como inválidos. A ausência de correspondências termina localmente sem chamar
o provider. O mecanismo reduz exposição e contexto, mas não valida a verdade semântica.

## Segurança passiva de URL (v0.13.0)

`PassiveUrlAnalyzer` usa somente `urllib.parse`, `ipaddress`, IDNA da biblioteca
padrão e regras determinísticas. O analisador não possui cliente HTTP nem função de
DNS. Normaliza o hostname, remove userinfo da representação canónica, identifica
destinos locais/não globais e grava apenas uma impressão digital na auditoria.
Pontuação é triagem explicável; não equivale a reputação ou prova de segurança.

## Reputação externa de URL (v0.14.0)

`VirusTotalUrlReputation` é um adaptador separado e não é chamado pela análise
passiva. O fluxo exige aprovação na invocação e chave no ambiente, reaplica a
análise local, bloqueia alvos evidentemente internos/ambíguos e só então constrói
um `GET` HTTPS para o relatório existente. Nunca chama o endpoint de submissão.

O ID remoto é Base64 URL-safe sem padding. Isto não anonimiza a URL: é reversível,
portanto a saída inclui aviso de privacidade. A integração devolve apenas estatísticas
limitadas e timestamp, não o corpo remoto completo. Timeout e bytes são limitados,
erros são sanitizados e a chave não entra no log. A defesa não faz DNS e não deteta
split-horizon; essa decisão evita que a própria validação passiva faça rede.

## Catálogo CISA KEV (v0.15.0)

`CisaKevCatalog` separa aquisição e utilização. `update` é a única operação de
rede: exige aprovação, usa um URL HTTPS constante, limita bytes/tempo e valida o
documento completo antes de qualquer substituição. O JSON oficial é preservado
byte a byte, com escrita temporária, `fsync`, permissões 0600 quando suportadas e
`os.replace`; assim, falha de rede ou esquema não corrompe um cache válido.

`check` valida o formato CVE, lê no máximo 10 MiB e pesquisa apenas a lista local.
Não existe atualização implícita, consulta NVD ou provider de IA neste fluxo. A
resposta inclui hash do cache para permitir reproduzir a decisão. A validação é
deliberadamente compatível com campos adicionais, mas exige o núcleo publicado
pela CISA, contagem exata, CVEs únicos e datas ISO.

## Análise estática Python (v0.16.0)

`BanditScanner` é um adaptador opcional e read-only. Antes do subprocesso resolve
um caminho relativo contra a pasta-base, rejeita fuga e links simbólicos e percorre
a árvore sem os seguir. O preflight limita número/tamanho de `.py` e exclui caches,
ambientes virtuais, VCS, builds e `node_modules`.

O comando é uma lista fixa iniciada pelo mesmo interpretador Python, com módulo
`bandit`, formato JSON, thresholds controlados e `--exit-zero`; não existe shell,
argumento livre vindo do modelo. Na v0.17 usa -I -B, cwd privado, INI/YAML vazios
explícitos e --ignore-nosec. Não carrega configuração do projeto; plugins já
instalados no ambiente permanecem confiáveis. O subprocesso recebe
stdin fechado, timeout e ambiente sem `PYTHONPATH/PYTHONHOME`. O relatório fica num
diretório temporário fora do projeto, tem limite de bytes e é removido no final.
O limite é verificado após o processo, não durante a escrita. stderr é descartado.
Campos de observação de rede/escritas são null: não há monitorização de SO.

A normalização omite o campo `code`, converte caminhos para relativos e limita texto
e quantidade de achados. Isto reduz exposição, mas Bandit e o parser continuam a
correr no processo filho sem sandbox de sistema operacional. Código deliberadamente
hostil deve ser analisado num ambiente isolado.

## Próximo módulo

API implementada em gensia/api.py (v0.18): import opcional, nenhum import de
ferramentas pessoais, token obrigatório, dados de saída explicitamente limitados.
Lançador fixa loopback e desativa proxy headers/access log. Host e Origin validados
antes de servir os três endpoints GET. O token não pode viajar na query string.
O modelo de ameaça não inclui processos locais comprometidos nem proxy externo.

## Equipa de agentes (v0.19.0)

`gensia.agents.Coordinator` valida tarefas explícitas e delega sequencialmente.
`SecurityAgent` reutiliza PassiveUrlAnalyzer/BanditScanner; `ReviewAgent` recebe
evidências estruturadas com IDs, prioriza severidades e opcionalmente consulta
Ollama; `StudyAgent` reutiliza LocalDocumentSearch. Não há descoberta automática
de ferramentas nem execução de texto produzido pelo modelo. Erros esperados são
isolados por etapa; falhas de auditoria interrompem a operação. A CLI fixa o
provider Ollama local e a equipa recusa providers declarados como cloud.

O log guarda estados e hashes; relatórios impressos podem conter informação
sensível. Revisor recebe até 30 achados por scan, sem campo de código nem URL
completa. Tutor recebe trechos selecionados. Citações/recomendações não são prova
de correção. Não há workers permanentes, autoedição ou fallback cloud.
Detalhes em AGENT_TEAM.md. Na v0.19.1, o provider usa opener sem proxies e recusa
todos os redirecionamentos HTTP. Isto protege o destino da ligação; não prova que
um servidor local arbitrário não encaminhe dados. O operador deve usar modelos
instalados localmente e desativar funcionalidades cloud no servidor.
Bandit e API Ollama reais validados; inferência ainda pendente por falta de pesos.

## Diagnóstico local (v0.20.0)

`gensia.doctor` é uma CLI independente e não é invocada automaticamente pelos
agentes. Valida argumentos antes de verificar dependências ou rede. Verifica
Bandit por metadados e resolução do módulo, sem o importar; consulta apenas
GET /api/tags através do transporte local protegido. Não lê documentos nem memória.
Etiquetas exatas, sem aliases ou seleção automática. Não expõe inventário completo
nem corpos de erro HTTP. `preflight_passed` só significa pré-requisitos observados;
não valida execução Bandit, inferência nem a política interna do servidor Ollama.
Não inicia serviços nem downloads. Ver docs/DOCTOR.md.

## Catálogo read-only (v0.21.0)

`agent_catalog.py` contém apenas dataclasses imutáveis e metadados públicos. A CLI
obtém descrições dessa definição; a API não importa `agents.py` nem ferramentas.
`GET /agents` usa `CatalogSnapshot` como response_model, permitindo apenas campos
declarados. Schema version 1 distingue capacidades estáticas de estado runtime:
`not_observed`, `dependencies_checked=false`, `execution_exposed=false`.
Não consulta modelos, ficheiros ou processos. Guardas existentes mantêm token,
Host exato, rejeição de Origin, métodos mutáveis e query strings. Agora existem
quatro endpoints GET. Não há CORS, HTML nem rotas de execução de agentes.

## Painel experimental e diagnóstico atual (v0.32.0)

As secções anteriores descrevem incrementos históricos. Atualmente /agents/report
exporta HTML autenticado e /diagnostics inclui capacidades de proteção read-only.
Três rotas fixas /panel, /panel.js e /panel.css servem shell público sem dados/token.
Só GET /diagnostics admite Origin única local exata, com Bearer obrigatório;
não há CORS e as outras rotas de dados continuam a recusar Origin. Sec-Fetch-Site
presente deve ser same-origin/none, sem duplicados. Host/métodos/query permanecem
restritos. CSP do shell permite script/style/connect self, sem inline, form ou
framing; JSON continua com default-src none. Assets são código confiável do projeto,
não ficheiros do workspace pessoal. Nenhuma rota nova executa agentes/documentos.
Token vive só na sessão JS, com limpeza manual, abort e proteção contra respostas
tardias. Não é proteção contra navegador/extensões/processos locais comprometidos.
HTTP e controlo de fluxo JS testados; browser/layout/CSP reais ainda por validar.
Ver docs/PANEL.md e docs/PRODUCT_READINESS.md antes de qualquer piloto.
