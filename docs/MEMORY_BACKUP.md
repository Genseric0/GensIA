# Backup explícito de notas — v0.25.0

Na raiz do projeto (Windows, Python 3.10+):

```powershell
py -3 -m gensia memory backup --output notas.memory-backup.json
```

Para uma base específica:

```powershell
py -3 -m gensia memory --db caminho\memory.sqlite3 backup --output notas.memory-backup.json
```

A base de origem deve existir. A pasta de destino também; o ficheiro de destino
não pode existir. Código 0 indica sucesso e 6 uma falha controlada de memória.
Em Linux/macOS, usar `python3` em vez de `py -3`.

## Formato e garantias

JSON UTF-8: `schema_version: 1`, `kind: "gensia.memory_backup"`, `exported_at` com
fuso UTC e `notes`, uma lista de objetos `key`, `value`, `updated_at`. Preserva as
datas das notas e lê o conjunto por uma única consulta SQLite read-only. Usa o
motor SQLite, incluindo dados confirmados em WAL; não copia apenas o ficheiro .db.
Não exporta configurações, credenciais, auditoria, ficheiros ou modelos.

Limites: 1000 notas e 8 MiB de JSON serializado. Cada nota respeita chave até 100,
valor até 4000 e data até 64 caracteres, com data ISO válida e timezone. Dados
inválidos ou excesso de limite são recusados antes de criar o ficheiro; não há
backup truncado silenciosamente. Buffers e serialização têm overhead adicional;
8 MiB é o limite do ficheiro, não de toda a memória do processo.

Destino criado exclusivamente (O_EXCL), recusando ficheiros existentes e symlinks.
Em POSIX, modo inicial 0600; permissões Windows dependem da ACL herdada. Flush e
fsync são pedidos antes do sucesso. Falha de escrita/sync pode deixar ficheiro
incompleto, sem apagar ou substituir automaticamente esse destino. Não há rename
atómico ou fsync do diretório; não se promete resistência a todos os tipos de crash.
Diretórios-pai devem ser confiáveis, sem trocas concorrentes hostis.

O terminal mostra só contagem, tamanho e SHA-256 do ficheiro. O hash permite
comparação de integridade, mas não é assinatura nem prova de autenticidade.

## Dados sensíveis e continuidade

**O backup contém todas as notas em texto legível, sem encriptação.** Protege a
pasta e não o anexes ao repositório. O nome recomendado `*.memory-backup.json`
está no gitignore, que não protege ficheiros já tracked ou com outro nome.
Não há envio a serviços externos nem agendamento automático.

Restauro ainda não implementado nesta versão. Mantém a origem e não trates esta
exportação como recuperação completa já validada. O próximo incremento validará
o formato e criará uma DB nova sem substituir notas existentes.

## Validação

Nove testes novos usam SQLite real e dados sintéticos; incluem WAL com ligação
aberta e CLI real. Teste de fsync falhado é injetado. A suite passou com 204 testes,
sem omissões, em Linux. Nenhuma base pessoal foi lida. Windows real ainda pendente.
Reproduzir: `py -3 -m unittest discover -s tests -p test_memory_backup.py -v`.

Fonte primária consultada em 16/10/2026:
[SQLite — isolamento de leituras](https://www.sqlite.org/isolation.html).
Sem novas dependências de produção.
