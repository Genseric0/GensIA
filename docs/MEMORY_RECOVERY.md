# Verificação e recuperação da memória — v0.64.0

## Recuperação assistida numa cópia — 21/10/2026

Novo comando para uma base de notas GensIA local confiável em modo rollback.
Resolve o caso reproduzido na0.63: após cache spill e interrupção, um hot journal
impede a leitura read-only, porque SQLite precisa de escrever para fazer rollback.
A origem nunca é aberta pelo SQLite neste comando. Só são pedidos acessos de
leitura aos seus bytes; não são apagados, renomeados ou reparados os originais.

1. Parar a GensIA e todos os programas/processos que possam aceder à base e aos
   seus auxiliares. Preservar conjuntamente os originais; não apagar o journal.
2. Escolher uma pasta local confiável e um destino novo, sem quaisquer ficheiros
   `-journal`, `-wal` ou `-shm` desse destino. Ter espaço para várias cópias.
3. Usar Python3.11+ e as duas confirmações específicas:

```bash
python -m gensia memory --db notas.sqlite3 recover-copy --output recuperada-nova.sqlite3 --approve --source-stopped
python -m gensia memory --db recuperada-nova.sqlite3 check
```

`--source-stopped` é uma declaração do operador. O programa não termina outros
processos, não impõe lock à origem nem verifica a declaração. Não usar numa base
ativa ou num filesystem de rede. Os hashes e estatísticas detetam alterações
observadas; não criam snapshot atómico nem impedem escritas depois da última
observação. `source_quiescence_enforced:false` mantém essa limitação explícita.

O comando copia a base e o eventual journal para uma pasta privada na pasta do
destino, por blocos de64KiB, com teto64MiB por ficheiro. Recusa ficheiros especiais,
symlinks e hard links adicionais; compara identidade/tamanho/mtime/ctime antes e
depois da leitura, hashes SHA256 de origem/cópia e outra leitura da origem antes
de recuperar e antes de publicar. O acesso de leitura pode atualizar atime.
`source_hashes_verified:true` só descreve as comparações realizadas, não garante
ausência de escritores. Nenhum conteúdo de nota é incluído na saída.

Antes de abrir SQLite na cópia, recusa WAL tanto pelo header da base como pela
presença de `-wal`/`-shm`, e recusa trailers de super-journal. Também limita o
tamanho original declarado pelo journal, páginas e sectores, impedindo expansão
evidentemente excessiva antes dos limites SQL. Empty/zero journals são permitidos;
headers não vazios e inválidos são recusados. Não se copiam super-journals nem
se seguem os seus nomes para outros ficheiros. Apenas um journal rollback de
uma base é suportado. Casos WAL/multi-base precisam de procedimento separado.

SQLite recupera somente a cópia. São aplicados trusted_schema=OFF, limites de
strings/SQL/expressões e orçamento cooperativo VM/tempo. Recuperação interna e
I/O podem ocorrer fora do progress handler; não é deadline rígido nem sandbox
para bases/journals hostis. SQLite e o SO devem ser confiáveis e atualizados.

Depois valida notas/integridade, exige só a tabela memories e o índice automático
esperado, exporta notas validadas e reconstrói esquema canónico numa segunda base.
Não elimina silenciosamente tabelas/índices/triggers personalizados: recusa-os.
Até1000 notas e os limites de backupJSONv1 continuam aplicáveis. Faz nova validação
e publica o ficheiro completo com as guardas0.63. Não substitui a origem nem muda
a configuração para passar a usar a cópia: essa decisão continua com o operador.

Resultados incluem notas verificadas, número de ficheiros de origem e metadados
de publicação. Falha antes de publicar não cria o destino final. Avisos depois de
publicar indicam `do_not_retry:true`; limpeza não confirmada dá `recovered:false`
mesmo com `destination_published:true`. Inspecionar antes de qualquer repetição.
Interrupção pode deixar temporários privados com notas em texto simples, incluindo
JSON e journals; não existe limpeza automática de órfãos após crash. A janela de
hard link POSIX da0.63 mantém-se. Backups externos e retenção continuam necessários.

### Validação e revisão do incremento0.64

17 testes novos em test_memory_recovery.py: journal real criado por cache spill
e término de processo, origem/journal byte a byte preservados, chamadas SQLite
apenas nas cópias, consentimento exato, WAL com/sem auxiliares, super-journal com
sentinel externa preservada, header de expansão excessiva, mudanças observadas na
origem, destino/auxiliares existentes ou concorrentes, recusa de schema adicional,
ficheiros inválidos, falhas injetadas e avisos pós-publicação. Um teste de symlink
é específico POSIX. Não se recuperou base de cliente nem se simulou corte físico
de energia. Suíte/CI e pacote instalado em TEST_REPORT.md e PR1/checks.

Uma revisão defensiva auxiliar identificou guardas para WAL pelo header, ponteiro
super-journal, expansão pelo journal e auxiliares no destino. Essas guardas foram
implementadas e testadas; isto não equivale a auditoria independente certificada.
O restauro JSON também passou a recusar auxiliares antigos do destino antes de
ler o backup e novamente antes de publicar, preservando todos esses ficheiros.

Fontes primárias consultadas em21/10/2026, sem novas dependências:
[locking e hot journals SQLite](https://www.sqlite.org/lockingv3.html),
[headers da base/journal](https://www.sqlite.org/fileformat.html),
[pager.c oficial — readSuperJournal/readJournalHdr](https://github.com/sqlite/sqlite/blob/master/src/pager.c).
Código consultado através do endpoint público contents de SQLite no GitHub;
esta implementação não copia o pager nem substitui a recuperação SQLite.

## Publicação segura de backup e restauro — 21/10/2026

Falha reproduzida na v0.62: injetar ENOSPC no `os.fsync` de backup/restauro
produzia erro controlado, mas deixava o destino final visível. Agora ambos usam
`gensia/publication.py`: gravar num diretório temporário privado na mesma pasta
do destino, fazer flush/fsync, fechar e só depois publicar sem substituir.
POSIX usa hard link exclusivo; Windows usa rename, que recusa destino existente.
Não há fallback para uma cópia parcial se o filesystem recusar hard links.
Um concorrente que crie o destino durante a preparação conserva o seu ficheiro.
Nenhuma dependência nova; a pasta de destino precisa de ser confiável.

Resultados incluem `destination_published`, `file_synced`, `directory_synced`,
`staging_cleaned`, `warnings` e `do_not_retry`. Falha na sincronização da pasta
ou limpeza depois de publicar devolve aviso e `do_not_retry:true`: o destino
já existe. Não repetir automaticamente. `directory_synced:null` em Windows
significa que não existe fsync portátil de diretório; não confirma durabilidade.
`restored:false` com destino publicado significa que a limpeza não ficou
confirmada. `backup_created:true` só afirma que os bytes foram publicados,
não que o suporte físico sobreviverá a uma falha de energia.

Interrupção pode deixar uma pasta `.gensia-publish-*` com dados em texto simples.
No POSIX, interrupção entre link e limpeza pode deixar dois hard links para a
base restaurada completa: MemoryStore continua a recusá-la. Este caso tem teste
real; não se enfraqueceu a guarda. Preservar os artefactos, parar os processos e
usar um destino novo para novo restauro a partir do backup validado. Limpeza de
órfãos exige inspeção do operador; não existe rotina automática de remoção.
O restauro também precisa de espaço para a base de construção no diretório
temporário do SO e para a cópia privada na pasta de destino.

### Ensaios e limites

`tests/test_publication.py` e `tests/test_memory_failures.py` cobrem escrita
parcial/ENOSPC injetados, fsync falhado, competição de destino, avisos após
publicação, processos filhos terminados antes/depois da publicação, rollback
DELETE/WAL e SQLITE_FULL real via `PRAGMA max_page_count`. Tudo usa dados sintéticos.
Não se encheu o disco do host; não se testou corte de energia, falha do kernel,
filesystem de rede nem hardware do utilizador. Os checkpoints são determinados;
não são uma exploração exaustiva de todos os momentos possíveis de interrupção.

Foi reproduzido um hot rollback journal após cache spill e término do processo.
Leitura/check/backup em modo read-only podem falhar porque a recuperação SQLite
precisa de escrita. O teste verifica essa recusa e recuperação por ligação
explicitamente gravável apenas numa base sintética descartável. Na0.63 não havia
comando assistido; na0.64, recover-copy recupera só uma cópia e mantém a recusa
de reparação da origem. Não apagar/renomear journals de uma base real.
Parar a aplicação, preservar conjuntamente base e auxiliares antes de intervenção
e preferir restauro lógico validado para destino novo. O procedimento0.64 acima
tem limites explícitos; WAL, multi-base e reparação física permanecem pendentes.

Fontes primárias consultadas em 21/10/2026:
[Python os.rename/os.link](https://docs.python.org/3.12/library/os.html#os.rename),
[commit e hot journals SQLite](https://www.sqlite.org/atomiccommit.html),
[limite de páginas SQLite](https://www.sqlite.org/pragma.html#pragma_max_page_count).

## Verificação de integridade

`memory check` valida uma base existente sem reparar, exportar ou imprimir notas.
Requer Python 3.11 ou superior para aplicar limites por ligação no SQLite; o
restante núcleo conserva a compatibilidade declarada. CI cobre Python 3.12/3.13.

```bash
python -m gensia memory --db notas.sqlite3 check
```

Saída `0` exige: tabela SQLite normal `memories`, até 1000 notas válidas e sem duplicados,
e uma única resposta `ok` do `PRAGMA integrity_check(1)`. Validação lógica e
estrutural partilham uma transação de leitura. Valores, chaves e erros internos
SQLite não são devolvidos; apenas contagem e metadados. Falha/inconclusivo dá
saída `6`. Base ausente não é criada. Links e ficheiros especiais usam as recusas
já existentes de MemoryStore. Views não substituem a tabela de notas.

## Limites e significado

- Limites SQLite por ligação: 1 MiB para strings/BLOB/linha, 64 KiB para SQL e
  profundidade de expressão 50. Não modificam limites globais do processo.
- Progress handler a cada 1000 instruções, com teto de 2 milhões de instruções e
  prazo de 2 s verificado durante trabalho SQL e antes do sucesso. Não é um
  deadline de parede rígido: espera de lock, I/O e encerramento podem demorar
  mais. O timeout de lock do MemoryStore permanece 5 s.
- Mais de 1000 notas, estruturas incompatíveis ou trabalho acima dos limites
  não recebem aprovação parcial. O comando não repara corrupção nem cifra dados.
- `mutations_requested:false` significa que não são pedidos INSERT/UPDATE,
  DELETE, checkpoint, VACUUM ou reparação. SQLite pode usar locks e ficheiros
  auxiliares de WAL; processos concorrentes podem alterar a base independentemente.
- O resultado é um snapshot, não um certificado permanente. Não verifica chaves
  estrangeiras nem toda a semântica de esquemas personalizados. Não é sandbox
  para ficheiros deliberadamente hostis e não substitui bibliotecas atualizadas.
- `recovery_tested:false` é intencional: verificar integridade não demonstra que
  um backup externo existe nem que o hardware recupera de falha de energia.

## Ensaio de recuperação sem substituir dados

Usar sempre destinos novos e guardar backups fora do repositório. Backups são
texto simples; proteger o destino e confirmar espaço disponível.

```bash
python -m gensia memory --db notas.sqlite3 check
python -m gensia memory --db notas.sqlite3 backup --output ensaio.memory-backup.json
python -m gensia memory --db recuperada-nova.sqlite3 restore --input ensaio.memory-backup.json --approve
python -m gensia memory --db recuperada-nova.sqlite3 check
python -m gensia memory --db recuperada-nova.sqlite3 list
```

Não eliminar a base original. Consultar explicitamente notas de teste na base
recuperada para confirmar conteúdo. Se a origem estiver corrompida, preservar os
ficheiros originais e auxiliares para diagnóstico; recuperar de um backup já
verificado para uma base nova. Não existe reparação física automática neste módulo.

## Evidências e fontes

Onze testes novos em `tests/test_memory_check.py`: bases válidas/vazias,
inexistentes e não SQLite; corrupção real de página e de índice secundário;
notas inválidas/duplicadas; view recusada antes da expressão; limites reais de
alocação e interrupção VM; WAL confirmado versus transação pendente; backup e
restauro para base nova; códigos CLI e ausência de conteúdo privado na saída.
Um teste preliminar baseado no resultado de CHECK não demonstrou a garantia de
alocação pretendida. Foi substituído por uma consulta real que confirma que a
ligação recusa BLOB acima do limite com SQLITE_TOOBIG, sem inferir a semântica
de CHECK arbitrário a partir desse resultado. Não se omitiram testes Windows.

O verificador do wheel instala o pacote sem rede numa venv nova, fora do checkout,
restaura notas sintéticas e executa a CLI `memory check` sobre a base recuperada.
São sete etapas; a aprovação não exige API, modelos ou motores de voz.

Fontes primárias consultadas em 21/10/2026:

- [SQLite: integrity_check](https://www.sqlite.org/pragma.html#pragma_integrity_check)
- [SQLite: proteção contra entradas não confiáveis](https://www.sqlite.org/security.html)
- [Python: setlimit e progress handler](https://docs.python.org/3.12/library/sqlite3.html)

SQLite e sqlite3 já eram utilizados; nenhuma dependência foi adicionada.
