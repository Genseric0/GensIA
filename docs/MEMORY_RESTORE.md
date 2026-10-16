# Restauro explícito para base nova — v0.26.0

Na raiz do projeto, depois de gerar o backup, em Windows/Python 3.10+:

```powershell
py -3 -m gensia memory --db recuperada.sqlite3 restore --input notas.memory-backup.json --approve
py -3 -m gensia memory --db recuperada.sqlite3 list
py -3 -m gensia memory --db recuperada.sqlite3 get tema
```

`--db` designa o destino. A pasta-pai tem de existir e a base não pode existir,
mesmo vazia. Sem `--approve`, a operação é recusada antes de ler o backup. Usa
`python3` em Linux/macOS. Código 0 indica sucesso; 6 indica erro controlado.
`get` só encontra a chave do exemplo se ela existir no teu backup e mostra o valor.

## Validação e escrita

Aceita apenas JSON UTF-8 do formato v1 descrito em [MEMORY_BACKUP.md](MEMORY_BACKUP.md).
Recusa ficheiros de entrada não regulares/symlinks, mais de 8 MiB, notas acima de
1000, campos desconhecidos/duplicados, tipos incorretos, datas sem timezone ou
inválidas, chaves duplicadas e texto fora dos limites. Também recusa NaN/Infinity,
floats e escapes Unicode isolados. Limita a leitura mesmo se o ficheiro crescer.
Não executa SQL nem código contido no backup.

Só depois de validar todos os dados constrói uma DB SQLite temporária com schema
conhecido e INSERT parametrizado. Preserva datas/valores e verifica integrity_check.
Fecha a DB temporária e copia o resultado para um ficheiro criado exclusivamente
(O_EXCL, 0600 em POSIX), usando o descritor aberto. SQLite não abre o destino.
Não substitui ficheiros ou links e não mistura com notas de uma DB existente.

Uma falha de escrita/sync pode deixar a **nova DB incompleta**, com erro explícito.
Não a utiliza ou apaga automaticamente. A origem JSON e a DB anterior são
preservadas. O comando não altera o caminho padrão da memória: para usar a base
restaurada, continua a indicar `--db recuperada.sqlite3`.

## Limitações

- Dados JSON, DB temporária e DB final não estão encriptados. Protege pastas,
  backups e ACL; o modo POSIX não é uma garantia de permissões Windows.
- O SHA-256 do backup no resumo permite comparação; não autentica a origem.
- Pastas-pai/temporárias devem ser confiáveis. Não é sandbox de SO nem defesa
  contra outro processo hostil com as mesmas permissões.
- Flush/fsync do ficheiro não equivale a publicação atómica/recuperação após todos
  os tipos de crash. Não há fsync de diretório, merge ou migração de versões.
- O limite de 8 MiB é de entrada; objetos JSON e a DB têm overhead. Não existe
  quota de memória/CPU do parser JSON nem processo isolado nesta etapa.

## Evidência de 16/10/2026

Doze testes novos em `tests/test_memory_restore.py`: ciclo backup/restauro real,
preservação de origem/datas, CLI, aprovação, recusa de destinos, estruturas inválidas,
JSON inválido/duplicado, limites, base vazia, payload SQL e falhas de escrita.
Suite completa: 216 testes passaram com HTTP real e sem omissões em Linux.
Bandit 1.9.4 sem achados no novo módulo. Nenhum dado pessoal usado; Windows real
e interrupção abrupta do processo durante cópia continuam pendentes.

Reproduzir: `py -3 -m unittest discover -s tests -p test_memory_restore.py -v`.
Fontes primárias consultadas em 16/10/2026:
[Python JSON](https://docs.python.org/3.12/library/json.html),
[Python sqlite3](https://docs.python.org/3.12/library/sqlite3.html).
Sem novas dependências de produção.
