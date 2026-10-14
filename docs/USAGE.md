# GensIA — módulo 18 (v0.18.0)

## API local opcional (estado e diagnóstico)

Na pasta extraída, usando Python >=3.10:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
$env:GENSIA_API_TOKEN = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))")
.\.venv\Scripts\python.exe -m gensia.api
```

Token fica apenas no ambiente desse terminal. Para consultar, interrompe o servidor
com Ctrl+C e reinicia-o noutro terminal com o mesmo token, ou usa um cliente que
receba o token com segurança. Exemplo de pedido no terminal cliente:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/status -Headers @{Authorization="Bearer $env:GENSIA_API_TOKEN"}
```

O terminal cliente deve ter o mesmo GENSIA_API_TOKEN; não o partilhes nem o coloques
na URL. Remove a variável ao terminar: Remove-Item Env:GENSIA_API_TOKEN.

GET /health confirma o processo; GET /status mostra versão e modo;
GET /diagnostics lista Python e versões de dependências, sem contactar modelos.
Não expõe documentos, memória, caminhos, variáveis de ambiente ou ferramentas.
Só o lançador fornecido garante bind 127.0.0.1; não usar proxy, encaminhamento de
portas ou Uvicorn externo com host 0.0.0.0. Host deve ser 127.0.0.1:PORTA.
Pedidos com Origin, métodos diferentes de GET e query strings são recusados.
Sem CORS, Swagger/CDN, OpenAPI público ou access log. Token protege também /health.
O serviço não arranca automaticamente, não tem TLS nem defesa completa contra
outros processos locais maliciosos. Ainda não existe interface gráfica.

FastAPI 0.143.0 (MIT) e Uvicorn 0.54.0 (BSD-3-Clause) são opcionais.
Versões diretas fixadas; dependências transitivas ainda não têm lock com hashes.

Assistente local modular por terminal, com Ollama opcional e primeiras ferramentas
do sistema protegidas por pasta-base, lista fechada e confirmação explícita.
Não executa comandos livres produzidos pelo modelo.

## Executar no Windows

Requisito: Python 3.10 ou superior. Extrair o ZIP, abrir um terminal na pasta
que contém este README e executar:

```powershell
py -3 -m gensia doctor
py -3 -m gensia chat
```

## Ollama local

```powershell
ollama list
py -3 -m gensia --provider ollama doctor
py -3 -m gensia --provider ollama --model NOME_DO_MODELO chat
```

O modelo deve existir previamente. A ligação é limitada a localhost e a GensIA
não descarrega modelos nem usa fallback automático para cloud.

## Listar uma pasta autorizada

Escolhe uma pasta-base. O caminho final deve ser relativo e permanecer dentro dela:

```powershell
py -3 -m gensia tool list --workspace "C:\Users\UTILIZADOR\Documents" .
py -3 -m gensia tool list --workspace "C:\Users\UTILIZADOR\Documents" Faculdade
```

A listagem não é recursiva, devolve no máximo 200 itens por padrão e não lê o
conteúdo dos ficheiros. Caminhos absolutos e tentativas com `..` são recusados.

## Abrir aplicação permitida

Disponível apenas no Windows e sempre com confirmação explícita:

```powershell
py -3 -m gensia tool open-app calculator --approve
py -3 -m gensia tool open-app notepad --approve
py -3 -m gensia tool open-app files --approve
```

Sem `--approve`, a ação é recusada. PowerShell, CMD e comandos personalizados não
estão na lista permitida. A implementação usa lista de argumentos e `shell=False`.

## Auditoria

As ferramentas registam data, ação, resultado e uma impressão digital do alvo em
`.gensia/audit.jsonl`. Caminhos e conteúdo não são gravados. Outro destino pode
ser escolhido com `tool --audit FICHEIRO`.

Códigos: 0 sucesso; 2 entrada inválida; 3 modelo indisponível; 4 permissão
recusada; 5 erro da ferramenta; 6 erro de memória; 7 erro de voz; 8 erro de
documento; 9 erro de análise de segurança.

## Memória local explícita

Na pasta do projeto, executar:

```powershell
py -3 -m gensia memory set idioma "Português"
py -3 -m gensia memory get idioma
py -3 -m gensia memory list
py -3 -m gensia memory delete idioma --approve
```

`set` guarda ou substitui a chave indicada. Chaves: 1–100 caracteres;
valores: 1–4000 caracteres. `list` mostra chaves e datas, com paginação
`--limit 50 --offset 0`. Uma chave inexistente devolve null em `get`.
Erros de memória usam código de saída 6.

O ficheiro padrão é `.gensia/memory.sqlite3` dentro da pasta pessoal do
utilizador, independente da pasta onde inicia a aplicação. Para escolher
outro ficheiro: `memory --db CAMINHO set CHAVE VALOR`.
Consultar memória vazia não cria ficheiros. Não há gravação automática de
conversas ou envio destas notas ao modelo. O campo `persistent_memory=false`
em status descreve o chat; `memory_available=true` indica a ferramenta disponível.

A base não é encriptada. Não usar para passwords ou tokens; texto passado na
linha de comandos pode ficar no histórico do terminal. Apagar uma nota remove-a
das consultas, mas não garante eliminação forense de backups ou do disco.

## Documentos locais: TXT e Markdown

Lê explicitamente um documento dentro de uma pasta-base autorizada:

```powershell
py -3 -m gensia document `
  --workspace "C:\Users\UTILIZADOR\Documents\Faculdade" `
  read "Redes\aula-nat.md"
```

Para criar um resumo de estudo com um modelo já instalado no Ollama local:

```powershell
py -3 -m gensia --provider ollama --model NOME_DO_MODELO document `
  --workspace "C:\Users\UTILIZADOR\Documents\Faculdade" `
  summarize "Redes\aula-nat.md" --style study
```

O estilo `study` produz ideias principais, conceitos-chave, exemplo prático e
perguntas de revisão; `--style concise` pede até cinco pontos. O endpoint Ollama
continua limitado a localhost, sem credenciais ou fallback cloud.

São aceites apenas `.txt`, `.md` e `.markdown` em UTF-8. Caminhos absolutos,
`..`, links simbólicos e conteúdo binário são recusados. O limite padrão é
64 KiB; leitura simples permite `--max-kib` até 256, enquanto resumo permanece
limitado a 64 KiB. Ficheiros maiores não são truncados silenciosamente.

O texto só é enviado ao provider no comando `summarize`. É delimitado como dado
não confiável, não como instrução; isso reduz, mas não elimina completamente,
riscos de prompt injection. A saída do modelo pode conter erros e deve ser
conferida contra o documento. A auditoria grava apenas uma impressão digital do
caminho, nunca o texto.

## PDF local com texto incorporado

Instala a dependência opcional e extrai apenas o texto de um PDF escolhido:

```powershell
py -3 -m pip install -U pypdf
py -3 -m gensia document --workspace "C:\Users\UTILIZADOR\Documents" pdf-read "aula.pdf"
py -3 -m gensia --provider ollama --model NOME_DO_MODELO document `
  --workspace "C:\Users\UTILIZADOR\Documents" pdf-summarize "aula.pdf" --style study
```

O padrão é 10 MiB e 25 páginas; os tetos são 50 MiB e 100 páginas
(`--max-mib` e `--max-pages`). PDFs encriptados, links simbólicos, caminhos fora
da pasta-base e extrações acima de 200 000 caracteres são recusados. O resumo
aceita até 60 000 caracteres e só envia texto ao Ollama local.

Faz uma pergunta específica e pede referências às páginas:

```powershell
py -3 -m gensia --provider ollama --model NOME_DO_MODELO document `
  --workspace "C:\Users\UTILIZADOR\Documents" `
  pdf-ask "aula.pdf" "Qual é a diferença entre NAT e PAT?"
```

A resposta deve citar páginas como `[p. 2]`. A GensIA recolhe essas páginas,
confirma se estão dentro do intervalo real e devolve `citation_status`. `missing`
ou `invalid` produz um aviso. A verificação é sintática: uma página existente não
garante que a afirmação esteja realmente sustentada nela. Quando a informação não
existir, o modelo deve responder `NÃO ENCONTRADO NO DOCUMENTO.`. A pergunta aceita
até 2000 caracteres.

Não há OCR: PDFs digitalizados apenas como imagem devolvem erro. Ordem, tabelas e
colunas podem não reproduzir o layout. O parser corre no processo principal; os
limites reduzem consumo excessivo, mas não são uma sandbox para PDFs não confiáveis.

## Pesquisa local em vários documentos

Pesquisa trechos relevantes sem iniciar o Ollama e sem criar um índice persistente:

```powershell
py -3 -m gensia document `
  --workspace "C:\Users\UTILIZADOR\Documents\Faculdade" `
  search "endereços NAT" "Redes\aula.md" "Redes\manual.pdf" --top-k 5
```

Aceita uma combinação explícita de até dez ficheiros TXT, Markdown e PDF. O ranking
TF-IDF é calculado em memória e é insensível a maiúsculas e acentos. Cada resultado
inclui caminho relativo, trecho, pontuação e linhas ou página. Não há varrimento
automático da pasta, embeddings, ChromaDB, cloud ou envio ao modelo. A pesquisa é
lexical: sinónimos sem termos em comum podem não ser encontrados, e a pontuação só
serve para ordenar os documentos desta execução.

## Resposta fundamentada em vários documentos

Recupera primeiro os melhores trechos e envia somente esses trechos ao Ollama:

```powershell
py -3 -m gensia --provider ollama --model NOME_DO_MODELO document `
  --workspace "C:\Users\UTILIZADOR\Documents\Faculdade" `
  ask-search "Qual é a diferença entre NAT e PAT?" `
  "Redes\aula.md" "Redes\manual.pdf" --top-k 5
```

Cada trecho recebe um identificador e a resposta deve citar `[fonte N]`. A GensIA
confirma se o identificador existe e devolve `citation_status`. Se a pesquisa não
encontrar correspondências, responde localmente `NÃO ENCONTRADO NOS DOCUMENTOS.`
sem chamar o modelo. Uma referência válida confirma apenas que a fonte foi
recuperada; não prova que a afirmação esteja semanticamente correta. Não existe
fallback cloud, índice persistente ou envio dos documentos completos ao provider.

## Cibersegurança: análise passiva de URL

Analisa uma URL sem a abrir, resolver DNS ou contactar serviços de reputação:

```powershell
py -3 -m gensia security url "https://example.com/login"
py -3 -m gensia security url "http://127.0.0.1/admin"
```

São avaliados esquema HTTP/HTTPS, hostname normalizado, `userinfo`, IP literal,
endereços não públicos, Punycode, porta não padrão, número de subdomínios e
tamanhos invulgares. Credenciais antes de `@` são removidas da URL canónica e a
auditoria não grava a URL original. Esquemas como `file:` e `javascript:`, controlos,
portas inválidas e hostnames malformados são recusados.

`risk_level` é triagem heurística, não veredicto. Mesmo `low` exige revisão: este
módulo não consulta DNS, certificado TLS, redirecionamentos, conteúdo, reputação,
CISA KEV, VirusTotal ou malware. Referências: RFC 3986 e OWASP SSRF Prevention.

## Cibersegurança: reputação externa opt-in

É possível consultar um relatório **já existente** no VirusTotal API v3. Esta é
uma ação externa separada: requer uma chave no ambiente e confirmação explícita.
Não existe submissão para análise nem fallback automático.

```powershell
$env:VIRUSTOTAL_API_KEY = "A_TUA_CHAVE"
py -3 -m gensia security url-reputation "https://example.com/" --approve-external
Remove-Item Env:VIRUSTOTAL_API_KEY
```

Não passes a chave como argumento, para evitar o histórico do terminal. A GensIA
faz apenas `GET /api/v3/urls/{id}` por HTTPS, com `x-apikey`; `{id}` é a URL
canónica em Base64 URL-safe sem `=`. Apesar de codificado, esse identificador é
reversível e divulga a URL ao VirusTotal. Avalia a política de privacidade e os
termos/quota da tua conta antes de usar.

Sem `--approve-external` ou `VIRUSTOTAL_API_KEY`, nada é contactado. URLs com
userinfo, IP não público, hostname de uma só etiqueta e sufixos locais comuns são
recusadas antes da rede. A validação não resolve DNS, portanto um domínio público
que internamente resolva para rede privada continua a ser uma limitação real.

HTTP 404 significa apenas que não existe relatório. Zero motores a assinalar uma
URL também não é prova de segurança. A resposta é limitada a 1 MiB, o timeout pode
ser ajustado com `--request-timeout` (1–60 segundos) e a chave/URL não são gravadas
em claro na auditoria.

## Cibersegurança: catálogo CISA KEV local

O catálogo **Known Exploited Vulnerabilities** ajuda a priorizar CVEs com evidência
de exploração no mundo real. O download é uma ação externa explícita e separada;
depois dele, cada consulta é feita apenas no ficheiro local:

```powershell
# Único passo que contacta a CISA
py -3 -m gensia security kev-update --approve-external

# Consulta local; não usa rede
py -3 -m gensia security kev-check CVE-2021-44228
```

O cache padrão é `$env:USERPROFILE\.gensia\cisa-kev.json`. Para escolher outro:

```powershell
py -3 -m gensia security kev-update --cache ".\dados\cisa-kev.json" --approve-external
py -3 -m gensia security kev-check CVE-2021-44228 --cache ".\dados\cisa-kev.json"
```

A atualização aceita somente o URL oficial fixo, limita a resposta a 10 MiB,
valida UTF-8/JSON, metadados, contagem, CVEs únicos, campos e datas antes de fazer
uma substituição atómica. Um download inválido não destrói o cache anterior; se o
conteúdo for idêntico, o ficheiro não é reescrito. Links simbólicos são recusados.

Cada resultado inclui a versão, data de publicação e SHA-256 do cache. Não encontrar
uma CVE não prova que ela não seja explorada: o cache pode estar desatualizado e o
KEV não é uma lista completa de todas as vulnerabilidades. A `dueDate` é vinculativa
no contexto de agências federais civis dos EUA; fora desse âmbito deve ser tratada
como sinal de priorização, não como prazo legal local. Não há atualização automática.

## Cibersegurança: análise estática Python com Bandit

O Bandit é opcional e corre localmente. Instala a versão validada e analisa um
ficheiro ou projeto explicitamente escolhido dentro de uma pasta-base:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install bandit==1.9.4

.\.venv\Scripts\python.exe -m gensia security bandit `
  --workspace "C:\Users\UTILIZADOR\Documents\Projetos" `
  "meu-projeto" --severity low --confidence low
```

Também é possível indicar um único ficheiro `.py`. O caminho deve ser relativo e
permanecer dentro de `--workspace`. A GensIA recusa travessia, alvos simbólicos e
links não autorizados na árvore; ignora diretórios gerados comuns como `.git`,
`.venv`, `venv`, `__pycache__`, `build`, `dist` e `node_modules`.

A execução usa `python -I -B -m bandit`, argumentos separados e `shell=False`,
num diretório temporário privado. O modo isolado exclui a pasta corrente e pacotes
do utilizador: instala Bandit no ambiente virtual usado para executar a GensIA,
não com `pip --user`. Ficheiros locais chamados `bandit.py` não são importados.
Configurações INI/YAML vazias explícitas substituem as do projeto; `# nosec` não
suprime achados. Plugins já instalados no ambiente continuam a ser confiáveis.
Não aceita comandos livres vindos do modelo. `PYTHONPATH` e
`PYTHONHOME` são removidos do subprocesso. Limites: 5000 ficheiros Python, 100 MiB
de código, relatório de 5 MiB, 500 achados devolvidos e timeout de 5–300 segundos.
O relatório temporário é eliminado e nenhum trecho de código é incluído no JSON da
GensIA. A auditoria guarda somente a impressão digital do alvo.

O Bandit constrói a AST do código e procura padrões de segurança; não se pede a
execução do projeto nem correções. Não há sandbox do SO ou monitorização de rede e
escritas: `network_accessed` e `files_modified` são `null` (desconhecido), não provas
de ausência. O limite do relatório é verificado depois do processo, não uma quota
de disco. Não analisar árvores modificadas simultaneamente. Mesmo sem achados,
o código não deve ser considerado
seguro: análise estática tem falsos positivos/negativos, não verifica dependências
e não substitui revisão humana, testes ou isolamento para código não confiável.

## Voz local: transcrever um ficheiro

Esta função é opcional. A GensIA base continua sem dependências externas. Para a
ativar, instala o pacote oficial OpenAI Whisper e o FFmpeg no próprio computador:

```powershell
py -3 -m pip install -U openai-whisper
choco install ffmpeg
```

Depois, transcreve um ficheiro que escolheste explicitamente:

```powershell
py -3 -m gensia voice transcribe "C:\Audio\nota.wav"
py -3 -m gensia voice transcribe "C:\Audio\meeting.mp3" --language auto
py -3 -m gensia voice transcribe "C:\Audio\aula.flac" --model small --language pt
```

O padrão é `base`, português e CPU. Formatos aceites: WAV, MP3, FLAC, M4A, OGG e
WebM, até 500 MiB. `--device cuda` é opt-in. O Whisper pode descarregar os pesos do
modelo selecionado na primeira utilização; depois a inferência é local. O áudio e
a transcrição não são gravados pela GensIA, enviados ao Ollama ou enviados à cloud.
Para deteção automática do idioma, usa `--language auto`.

O comando só lê o ficheiro e devolve JSON. Não abre o microfone. Links simbólicos,
formatos fora da lista e ficheiros acima do limite são recusados. `voice_enabled`
permanece `false` no estado até a dependência opcional ser detetada; `voice_available`
indica que o comando existe.

## Saída de voz local com Piper

Instalação opcional (o projeto Piper atual requer Python 3.9 ou superior):

```powershell
py -3 -m pip install -U piper-tts
mkdir "$env:USERPROFILE\.gensia\voices"
py -3 -m piper.download_voices pt_PT-tugão-medium --data-dir "$env:USERPROFILE\.gensia\voices"
```

O download é um passo explícito e separado. Verifica o `MODEL_CARD` da voz antes
de a usar ou distribuir: a licença da voz pode ser diferente da licença do Piper.
Para ver outras vozes disponíveis, executa `py -3 -m piper.download_voices`.

Cria um WAV sem o reproduzir automaticamente:

```powershell
py -3 -m gensia voice synthesize "Olá. A GensIA está a funcionar localmente." `
  --voice "$env:USERPROFILE\.gensia\voices\pt_PT-tugão-medium.onnx" `
  --output ".\fala.wav"
```

São obrigatórios o modelo `.onnx` e o respetivo `.onnx.json`. O texto é limitado
a 5000 caracteres. A escrita usa um ficheiro temporário e substituição atómica;
um WAV existente só é substituído com `--approve-overwrite`. O subprocesso recebe
uma lista de argumentos, usa `shell=False` e não contacta serviços externos.

## Captura limitada do microfone

Instala a dependência opcional `sounddevice`:

```powershell
py -3 -m pip install -U sounddevice
py -3 -m gensia voice devices
```

O segundo comando lista apenas dispositivos com entrada e os respetivos IDs.
Grava cinco segundos do microfone padrão para WAV PCM mono a 16 kHz:

```powershell
py -3 -m gensia voice record --output ".\pergunta.wav" --duration 5
```

Para escolher um dispositivo devolvido pelo primeiro comando:

```powershell
py -3 -m gensia voice record --output ".\pergunta.wav" --duration 10 --device 2
py -3 -m gensia voice transcribe ".\pergunta.wav" --language pt
```

A gravação só começa quando `voice record` é executado e termina automaticamente;
o máximo é 60 segundos. Não há escuta em segundo plano, reprodução, transcrição
automática ou envio para rede. O WAV é escrito primeiro num ficheiro temporário.
Perda de amostras cancela a operação, e substituir um destino existente exige
`--approve-overwrite`. No Windows, autoriza o acesso ao microfone nas definições
de privacidade se o sistema o solicitar.

## Limitações

As ferramentas e a voz ainda são chamadas explicitamente pela CLI; o Ollama não as chama.
Não há criação, alteração, movimentação ou eliminação geral de ficheiros. Não há
escuta contínua, reprodução automática de áudio, integração da memória no chat,
DOCX, OCR, browser ou envio de mensagens. A abertura de aplicações não
foi testada num computador Windows real.
