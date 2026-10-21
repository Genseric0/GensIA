# Auditoria defensiva — 21 de outubro de 2026

Estado: **RELEASE BLOCKED para distribuição comercial ou serviço multiutilizador**.
Este relatório descreve o endurecimento do agente local a partir da baseline
`206f4d1798d516deccb3268938777b1348cfb85b`. Não constitui certificação ASVS,
pentest de produção ou garantia de ausência de vulnerabilidades. A avaliação
global da API, interface e dados consta dos relatórios respetivos.

## Âmbito e modelo de confiança

Foram revistos `providers.py`, `tools.py`, `security.py`, `kev.py`, `voice.py` e
o tratamento de erros correspondente no terminal. Código e executáveis de
Whisper/Piper/Ollama, pesos, configuração do sistema operativo e diretórios de
trabalho são administrados pelo proprietário do computador. Um processo local
malicioso com os mesmos privilégios pode alterar esses componentes. O agente
não é uma fronteira de isolamento entre clientes.

A referência de organização é o [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0).
Aplicaram-se as áreas de validação, ficheiros, configuração, proteção de dados,
comunicação, autorização e logging/tratamento de erros. Não se declara cobertura
integral dos controlos, níveis ASVS ou verificação de IDs individuais.

## Problemas e correções verificadas

| Prioridade | Causa e risco | Correção | Evidência |
|---|---|---|---|
| P1 | Valores verdadeiros diferentes de `True` podiam autorizar efeitos. | `approved is True` para abrir aplicações, VT e KEV; a mesma regra protege substituição de áudio. | `test_action_security.py`, `test_voice_hardening.py` |
| P1 | Registar apenas o resultado permitia efeitos sem intenção auditada durável. | Intenção gravada antes do processo/pedido externo; JSONL com flush e fsync, ficheiro regular sem links, modo restrito. Falha de intenção bloqueia o efeito. | `test_action_security.py` |
| P1 | Uma falha de auditoria depois do efeito induzia repetição de uma ação já realizada. | Aplicação, VT e KEV devolvem resultado com `audit_completed: false` e aviso `do_not_retry`; o efeito não é repetido. Falhas de auditoria no terminal têm saída controlada 9. | `test_action_security.py` |
| P1 | Endpoint loopback, por si só, não exclui modelo cloud; proxies/redirecionamentos podiam divulgar prompts. | Proxy desativado, redirecionamentos recusados, nome cloud bloqueado e `/api/show` validado antes de cada prompt. Metadados remotos, incompletos ou malformados bloqueiam inferência. | `test_provider_hardening.py`, dois testes HTTP loopback em `test_provider_transport.py` |
| P1 | Respostas não confiáveis podiam incluir controlos de terminal ou JSON ambíguo. | Texto e UTF-8 limitados; ESC, C1, NUL e CR isolado recusados; CRLF normalizado; duplicados, NaN, infinito, overflow numérico e profundidade excessiva recusados. Erros públicos fixos omitem corpo HTTP e prompt. | `test_provider_hardening.py` |
| P1 | Whisper podia escolher a rotina de descarga de pesos e violar a expectativa de operação local. | Checkpoint `.pt` local explícito obrigatório antes de importar o motor; recusados links, diretórios, vazios e tamanho acima de 4 GiB. | `test_voice_hardening.py` |
| P1 | Texto privado do Piper em argumentos/logs de subprocesso e substituição de destino por corrida. | Texto por stdin, stdout/stderr descartados, sem shell, ficheiro temporário reservado e publicação exclusiva se não autorizada substituição. | `test_voice_hardening.py` |
| P2 | Cache KEV existente era lido integralmente durante atualização; symlink pendente não era recusado. | Leitura real limitada a 10 MiB + 1, inclusive após alteração de tamanho; symlink pendente recusado antes da rede. | `test_kev.py` |
| P2 | Corpos de erros HTTP VT/CISA podiam deixar descritores abertos. | `HTTPError.close()` sem consumir corpo. | Revisão de código e suíte security/KEV; sem teste específico de descritores VT/CISA |

## Evidências executadas

Executadas no ambiente de desenvolvimento Linux, com Python do `.venv`, dados
sintéticos e sem downloads de modelos. Comandos a partir da raiz:

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_provider*.py' -v
.venv/bin/python -B -m unittest discover -s tests -p 'test_voice*.py' -q
.venv/bin/python -B -m unittest discover -s tests -p test_action_security.py -v
.venv/bin/python -B -m unittest discover -s tests -p test_kev.py -q
.venv/bin/python -B -m unittest discover -s tests -p test_security.py -q
```

Resultados: **16 + 28 + 8 + 10 + 12 = 74 testes aprovados**, zero falhas nestes
cinco comandos. São testes direcionados; não equivalem à contagem global do
projeto. Os pedidos VT/CISA e as inferências foram simulados; apenas os dois
testes de transporte Ollama abriram servidores HTTP reais em loopback. Nenhuma
URL foi enviada ao VirusTotal, nem catálogo descarregado nestes testes.

Também executado `.venv/bin/python -m bandit -q gensia/providers.py gensia/tools.py
gensia/security.py gensia/kev.py gensia/voice.py`: dois alertas de severidade
baixa B404, relativos aos imports necessários de `subprocess`, zero médios e
zero elevados. Foram revistos: execução sem shell, argumentos controlados e
timeout para Piper. O resultado não é uma análise de dependências nem prova
de segurança dos executáveis/motores chamados.

## Limites e trabalho pendente

### API e interface: aplicabilidade ASVS

| Área | Controlo existente e evidência | Limite |
| --- | --- | --- |
| Autenticação e sessão | Bearer aleatório, header único, comparação constante; testes API/socket e browser | Um token por processo; expiração limpa a página, não revoga o servidor |
| Autorização | Diagnóstico e conversa autenticados; chat sem despacho de ferramentas; ações CLI exigem aprovação específica | Sem identidade de cliente, RBAC ou isolamento multiutilizador |
| XSS / conteúdo não confiável | textContent, CSP sem scripts inline, resposta Unicode limitada; teste Chromium de HTML | Sem auditoria integral de acessibilidade ou browser alternativo |
| CSRF / CORS | Sem cookies/CORS; Host e Origin exatos, query recusada; testes negativos HTTP | API limitada a loopback; não publicar diretamente |
| Validação / limites | JSON estrito, corpo32 KiB, contexto12000 caracteres, um worker de geração por aplicação | Lock é contenção de concorrência, não quota por cliente ou deadline total |
| SQL / dados | Queries parametrizadas e projeções limitadas; regressões de integridade e backup/restauro | Não cifra os dados em repouso nem controla processos com os mesmos privilégios |
| Passwords / recuperação / upload web | Não implementados ou expostos nesta aplicação local | Exigem desenho próprio antes de um serviço de clientes |

O cliente não envia prompts para serviços cloud automaticamente. A política de
metadados não controla o comportamento interno de um daemon Ollama comprometido.
Não se atribui um nível ASVS nem se apresentam controlos não testados como PASS.

- A confirmação `confirmed_local` significa que os metadados fornecidos pelo
  Ollama satisfazem a política; não é atestação criptográfica nem medição de
  tráfego do daemon. `status` conserva os indicadores de localidade/inferência
  não verificadas. Um daemon malicioso pode mentir ou mudar depois da verificação.
- O timeout HTTP é de operações de socket, não um deadline total de parede.
  Deve acrescentar-se supervisão de processo/requisição antes de oferecer SLA.
- O JSONL tem intenção durável, mas não é armazenamento imutável, assinado ou
  resistente a alterações por processos do mesmo utilizador. Falta rotação e
  política de retenção. fsync do ficheiro não garante persistência da entrada
  do diretório após falha súbita do sistema.
- Checkpoints/vozes devem ter origem e hash verificados pelo operador. O código
  não autentica pesos nem isola os motores ou FFmpeg do sistema operativo.
  `network_isolated: false` no Piper é intencional.
- A avaliação de symlinks, caminhos e metadados não elimina todas as corridas
  em diretórios mutáveis por outro processo com os mesmos privilégios.
- Não foi executado fluxo real de inferência, áudio, microfone ou abertura de
  aplicações Windows. Não foram executados ZAP, CodeQL, Semgrep, Gitleaks,
  OSV-Scanner ou Trivy por este incremento. Os resultados de dependências/CI
  devem ser consultados no relatório global.
- Envio de emails e execução autónoma de comandos arbitrários não foram
  acrescentados. A confirmação geral da missão não autoriza ações externas
  em nome de clientes.

Para venda e uso por clientes, permanecem critérios separados: distribuição
reproduzível e assinada, licenças dos modelos e vozes, segregação de dados,
autenticação/autorização do produto publicado, atualização segura, recuperação,
testes nos sistemas alvo e avaliação independente. Os testes acima não
justificam apresentar estas capacidades como concluídas.

## Referências primárias

### Atualização0.64 — recuperação em cópia — 21/10/2026

Novo memory_recovery.py mantém SQLite afastado da origem e recupera só clone
privado, com consentimento exato, limites e validação. Recusa WAL pelo header e
auxiliares, super-journal por magic no trailer e tamanho de rollback excessivo
antes de abrir SQLite; recusa schema adicional e reconstrói notas canónicas.
Hash/estat é deteção observada de alteração, não prova de lock ou snapshot atómico.
P1 corrigido em memory_restore.py: destino principal ausente com journal antigo
podia produzir sucesso seguido de falha de leitura. Agora recusa todos os
auxiliares do destino, preservando-os. Testes/causa em DATABASE_VALIDATION.md.
17 testes novos, Bandit sem médios/elevados e scanner limitado sem assinaturas.
Sem novas dependências, avaliação intrusiva externa ou reparação de dados reais.
O modo não é sandbox para SQLite hostil e exige origem parada por operador.

### Atualização0.63 — integridade de ficheiros — 21/10/2026

Reproduzida exposição de destino incompleto após erro ENOSPC em fsync de
backup/restauro. Corrigida com publicação exclusiva de ficheiro previamente
sincronizado e fechado; testes preservam destino criado por concorrente.
Avisos depois de publicar não apresentam o destino como ausente. Sem ampliação
de permissões, reparação automática, nova dependência ou teste externo.
Bandit sem médios/elevados e scanner limitado sem assinaturas nesta revisão.
Os riscos de diretórios não confiáveis, mesmo UID, journals/órfãos, filesystem
e hardware permanecem explicitados em MEMORY_RECOVERY.md.

### Fontes do hardening inicial

- [OWASP ASVS, versão 5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0)
- [Ollama: API show](https://docs.ollama.com/api/show)
- [Ollama: FAQ e cloud](https://docs.ollama.com/faq)
- [CISA: catálogo KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- [VirusTotal: URL report](https://docs.virustotal.com/reference/url-info)

Nenhuma biblioteca nova foi adotada neste incremento de hardening. Não se
afirmam versões atuais dos motores, compatibilidade de hardware, direitos de
redistribuição de modelos ou resultados de benchmark.
