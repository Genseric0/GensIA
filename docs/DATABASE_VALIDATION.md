# Validação da memória e integridade de dados

## Incremento0.64 — 21/10/2026

Novo recover-copy: leitura de bytes da origem e journal, hashes/estat verificados,
recuperação SQLite só na cópia, notas/integridade verificadas, esquema normalizado
e publicação exclusiva. 17 regressões novas;suíte411 Python PASS local. Paragem
da origem é declaração do operador, não lock verificado. Só uma base GensIA em
rollback;WAL/multi-base/esquemas adicionais recusados. Ver MEMORY_RECOVERY.md.

| Problema | Causa/correção | Evidência |
| --- | --- | --- |
| Hot journal impedia leitura da origem | Rollback precisa de escrita; memory_recovery.py recupera somente cópia privada com consentimento | Teste com cache spill/kill recupera101 notas; originais mantêm hashes e continuam a recusar leitura |
| P1: restauro podia indicar sucesso com auxiliares antigos | memory_restore.py só verificava destino principal; ensure_new_database recusa também journal/WAL/SHM antes de preparar e antes de publicar | test_memory_recovery cobre todos os auxiliares e destino concorrente; nenhum é apagado |

Reprodução manual da baseline072cbc6 com dados sintéticos e journal copiado:
restored:true, seguida de erro na leitura read-only. Na versão corrigida, a
operação é recusada e o destino principal continua ausente. Não se demonstrou
nesse ensaio perda de notas ou divulgação entre utilizadores; não se afirma tal
exploração. Nenhuma base real foi recuperada ou alterada.

## Incremento0.63 — 21/10/2026

Antes: injeção ENOSPC em fsync deixava backup/base de destino parcialmente
publicados apesar de erro. Correção em memory_backup.py/memory_restore.py e
publication.py: preparação privada, flush/fsync/fecho e publicação sem substituir
destinos concorrentes. Resultado explicita falhas de limpeza/sincronização após
publicar e desaconselha repetição. Regressões em test_publication.py e
test_memory_failures.py:17 testes novos, incluindo término real de processos,
SQLITE_FULL, rollback DELETE/WAL, hot journal e janela de hard link POSIX.
Suíte completa394 PASS local. Manual, limites e fontes em MEMORY_RECOVERY.md.
Não se executou recuperação em dados reais ou ensaio físico de corte de energia.
Histórico da auditoria inicial abaixo; não representa nova auditoria comercial.

Revisão executada em 20/10/2026 sobre a base GitHub
`206f4d1798d516deccb3268938777b1348cfb85b` (v0.34.0). Os ensaios usam apenas
SQLite e ficheiros sintéticos em pastas temporárias. Nenhuma base de utilizador
foi aberta, migrada ou apagada. O sistema não implementa operações financeiras,
stock, pagamentos ou saldos: esses cenários não se aplicam à memória explícita.

## Modelo e estado inicial

`memories(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)`.
Chave até100 caracteres; valor até4000; timestamp ISO com fuso. Notas são locais,
explícitas e não são automaticamente enviadas ao modelo. `set` faz upsert por
chave; `delete` é uma operação destrutiva autorizada explicitamente. Backup JSON
schema1 limitado a1000notas/8MiB; restauro escreve exclusivamente numa base nova.
Não existe esquema de utilizadores, contas, RBAC ou segregação de clientes.

Baseline antes da correção:

```bash
python3 -B -m unittest discover -s tests -p 'test_memory*.py' -q
```

Resultado inicial:36 testes passaram em1.126s. A cobertura anterior não detetava
as falhas abaixo, reproduzidas separadamente com dados sintéticos.

| Problema reproduzido | Prioridade e implicação | Correção e evidência |
| --- | --- | --- |
| `delete(approved='false')` apagava uma nota | P1: autorização por valor truthy | Apenas `approved is True`; matriz de valores recusados mantém a nota |
| Base nova criada com modo0644 | P1: privacidade por omissão inadequada em POSIX | Criação exclusiva0600 antes de SQLite, comprovada com umask0 |
| Escrita por hardlink alterava o ficheiro de origem | P1: alvo da operação ambíguo | Exige ficheiro regular com link único antes da ligação; origem permanece byte-idêntica |
| `get` devolvia coluna adicional do schema | P1: divulgação fora do contrato | SQL explícito sem SELECT*, apenas key/value/updated_at |
| `get` materializava valor de1.000.000bytes | P1: fronteira de leitura sem limite | Corte BLOB em401/16001/257bytes e validação posterior; caso grande recusado |
| Backup exportava apenas prefixo antes do NUL | P1: perda silenciosa no backup | Projeção BLOB preserva NUL para recusa antes da criação do destino |
| Unicode inválido lançava UnicodeEncodeError depois de criar a base | P2: exceção bruta/artefacto vazio | UTF-8 estrito antes do acesso ao disco, erro de domínio |
| Paginação aceitava booleanos/decimais numa base ausente e strings lançavam TypeError | P2: contrato inconsistente | Inteiros exatos,limit1–200 e offset0–2^63−1,antes da consulta de existência |

## Comportamento depois da correção

`gensia/memory.py` passa a criar novos ficheiros exclusivamente com0600, a recusar
symlinks/hardlinks/FIFO antes da ligação e a usar URI SQLite ro/rw e
`PRAGMA trusted_schema=OFF`. O modo rw impede a recriação implícita do destino
quando ele desaparece após a criação inicial. Ficheiros antigos não têm as suas
permissões alteradas silenciosamente.

As consultas são SQL fixo e parametrizado. Projeções BLOB têm um byte de sentinela
acima do máximo de UTF-8 de quatro bytes por carácter; o parser recusa tipo SQLite
que não seja TEXT,UTF-8 inválido,campos excessivos,NUL e data inválida/sem fuso.
Valores truncados não são apresentados como registos válidos. `get` lê no máximo
dois candidatos e recusa chaves repetidas; `list` lê apenas chave/data,sem valor.
Uma linha inválida impede que a chamada devolva uma lista parcial.

`gensia/memory_backup.py` usa o mesmo parser e a mesma projeção limitada. Recusa
chaves duplicadas e valida todo o conjunto antes de abrir o destino. Mantém os
limites1000notas/8MiB,formatoJSONv1,criaçãoexclusiva0600 e flush/fsync. Não repara a
base de origem. Desde0.63, erro antes da publicação não expõe destino parcial;
pode restar área temporária privada. O backup é texto simples,sem cifragem;
o hash não é assinatura. Avisos após publicação exigem inspeção, não repetição.

O restauro existente exige True exato,esquema JSON estrito,UTF-8 válido,chaves
únicas e datas com fuso. Constrói uma base temporária transacional,executa
`PRAGMA integrity_check` e copia para descritor privado criado com O_EXCL0600.
Desde0.63, só publica no destino após flush/fsync/fecho; a criação exclusiva
preserva destinos concorrentes. Limites de filesystem e interrupções estão em
MEMORY_RECOVERY.md.
Nunca abre pelo SQLite uma base de destino preexistente nem substitui o original.

## Ensaios executados

```bash
python3 -B -m unittest discover -s tests -p 'test_memory*.py' -q
python3 -B -m unittest discover -s tests -p test_database_hardening.py -v
```

Depois das alterações:36 testes existentes passaram em1.660s;22 novos testes
passaram em0.391s,sem falhas ou omissões neste ambiente Linux/Python3.12.14/
SQLite3.53.1. Os resultados da suite agregada são registados em TEST_REPORT.md.

Fluxos essenciais verificados:

- Backup→restauro exclusivo numa base nova→get/search:emojis de quatro bytes nos
  limites,português,notas multilinha e timestamps preservados;hash do backup igual;
  base original byte-idêntica e integrity_check do destino igual aok.
- Concorrência:4 threads,15 chaves distintas por thread,mais uma nota inicial;
  61registos persistidos sem perda,integrity_check igual aok.
- Rollback:UPDATE seguido de violação da chave primária na mesma transação;
  MemoryError controlado e valor inicial preservado após rollback.
- Tipos NULL/int/float/BLOB,UTF-8 inválido,NUL,duplicados,última linha inválida,
  campos de1MiB e schema com coluna extra:nenhum backup inválido criado;origens
  permanecem byte-idênticas. CLI recusa com código6 sem payload privado/traceback.

## Limites e condições de entrega

Não há quota global de CPU/memória do SQLite nem da serializaçãoJSON. A projeção
limita os campos entregues ao Python,mas SQLite ainda pode percorrer e ordenar uma
base grande. Os1001registos são lidos para detetar excesso;8MiB é conferido após
serialização. Schema externo,views e bases adulteradas não são neutralizados por
esta validação. A descodificação assume armazenamentoUTF-8 da GensIA;bases externas
UTF-16 podem ser recusadas. O controlo de tipo/link verifica o alvo antes de SQLite;
não é defesa atómica contra troca concorrente dos ancestrais por outro processo.

As pastas,instalação e utilizador do SO devem ser confiáveis. Modos POSIX não
comprovam ACL Windows. A revisão não validou Windows/macOS,interrupção abrupta,
restauro após falha de energia ou recuperação física de base corrompida. Não cria
backups recorrentes nem configura um serviço autónomo. Uso com clientes partilhados
continua bloqueado enquanto não existir isolamento e autorização por cliente.
# Correções da primeira execução Windows —21/10/2026

O CI Windows/Python3.13 encontrou13 erros de limpeza em fixtures SQLite e duas
falhas na recusa de destinos simbólicos de backup/restauro. A aplicação já
fechava a conexão da memória em `finally`; os descritores abertos eram das
fixtures que usavam somente o contexto transacional `with sqlite3.connect()`.
As fixtures agora combinam `closing(connection)` com o contexto transacional,
preservando commit/rollback e fechando os handles antes da limpeza temporária.
Não se usou garbage collection nem se omitiu qualquer teste para resolver a falha.

No Windows, a criação pelo CRT pode seguir um link simbólico pendente mesmo
com `O_CREAT|O_EXCL`. Backup e restauro agora recusam o componente final com
`is_symlink()` antes dessa abertura. A exclusividade continua obrigatória;
a validação não constitui isolamento contra corridas de outro processo com
privilégios equivalentes em diretórios mutáveis.

Regressões novas confirmam a recusa antes de chamar o CRT, ausência de leitura
da origem no restauro recusado, fecho de conexões de leitura/escrita após sucesso
e após erros SQL/de aplicação, e rollback das alterações pendentes. Execução
local direcionada:38 testes memory/backup/restore e24 testes de hardening,
todos aprovados, sem omissões. A repetição Windows deve ser consultada no CI;
estes resultados Linux, por si só, não a substituem.
# Incremento v0.62.0 — 21/10/2026

Novo comando explícito `memory check`: verificação SQLite completa e validação
lógica limitada, sem devolver notas ou pedir mutações. Onze regressões novas
incluem corrupção física de página e índice, WAL e ensaio de restauro. O plano,
limites e comandos de recuperação estão em [MEMORY_RECOVERY.md](MEMORY_RECOVERY.md).
Não equivale a reparação física, teste de falha de energia ou aprovação comercial.
