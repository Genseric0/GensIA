# Pesquisa explícita nas notas — v0.23.0

Na raiz do projeto, com Python 3.10+ (Windows):

```powershell
py -3 -m gensia memory set estudo-redes "Rever DNS e propagação"
py -3 -m gensia memory search DNS
py -3 -m gensia memory search DNS --limit 10 --offset 10
```

O primeiro comando guarda uma nota de exemplo; os restantes apenas leem.
Para escolher outra base: `py -3 -m gensia memory --db notas.sqlite3 search DNS`.
Em Linux/macOS pode usar `python3` em vez de `py -3`.

## Semântica e limites

- Substring literal em `key` ou `value`, sensível a maiúsculas e acentos:
  `DNS` não encontra `dns`; `%` e `_` não são wildcards.
- Query não vazia, até 200 caracteres, sem NUL. Não faz normalização Unicode.
- JSON de notas completas (`key`, `value`, `updated_at`), ordenadas por chave.
- 20 resultados por omissão, limite entre 1 e 200; offset não negativo.
- Sem resultados ou DB inexistente: `[]`, código 0, sem criar ficheiros.
- Falha de memória/validação: código 6; erro de argumentos CLI: código 2.
- Consulta parametrizada, ligação read-only. Não modifica notas nem envia dados
  à rede, ao modelo ou a serviços de embeddings.

Ao contrário de `memory list`, **search mostra os valores** das notas encontradas.
Evita partilhar o terminal ou redirecionar resultados para ficheiros públicos.
O histórico da shell pode guardar a query. SQLite não está encriptado por este
módulo; protege a pasta e os backups com as permissões do sistema operativo.

É pesquisa simples, não semântica. O limite restringe os resultados, não o número
de linhas examinadas: bases grandes podem tornar a consulta lenta. Paginação não
é um snapshot entre comandos se outro processo alterar as notas entretanto.

## Validação

Sete testes específicos usam bases temporárias e notas sintéticas, incluindo um
subprocesso CLI real. Ver `tests/test_memory_search.py`. Nenhum dado pessoal ou
base do utilizador foi utilizado. Windows real e integração automática no chat
não foram testados nem implementados neste incremento.
