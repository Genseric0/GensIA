# Verificação e recuperação da memória — v0.62.0

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
