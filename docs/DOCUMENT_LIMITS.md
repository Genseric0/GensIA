# Leitura de documentos — limites da v0.24.2

A GensIA consulta primeiro o tamanho do ficheiro e depois lê, no máximo, o limite
configurado mais um byte para a aplicação. Esse byte permite recusar o documento
se tiver crescido após a primeira verificação. Não devolve conteúdo truncado como
se fosse um documento completo. O ficheiro é fechado também quando a leitura falha.

Os comandos mantêm-se, na raiz do projeto (Windows, Python 3.10+):

```powershell
py -3 -m gensia document --workspace . --max-kib 64 read exemplo.md
py -3 -m gensia document --workspace . pdf-read exemplo.pdf --max-mib 10 --max-pages 25
```

Usa ficheiros próprios existentes. TXT/Markdown aceitam 1–256 KiB (64 por omissão);
resumos aceitam até 64 KiB. PDF aceita 1–50 MiB (10 por omissão) e 1–100 páginas
(25 por omissão), requerendo pypdf instalado. A leitura local pode criar eventos
no ficheiro de auditoria. Nenhum comando acima contacta um modelo ou a cloud.

Na API Python, tamanhos devem ser inteiros, excluindo bool; a CLI já usa argumentos
inteiros. Um documento exatamente no limite continua permitido.

## Evidência e limites restantes

Seis regressões em `tests/test_document_limits.py`: crescimento TXT/PDF injetado
após stat, conteúdo/hash UTF-8 no limite, PDF no limite com parser simulado, tipos
inválidos e erro de I/O com encerramento do stream. Em 16/10/2026 a suite completa
passou com 188 testes e HTTP real, sem omissões; Bandit 1.9.4 não encontrou achados
no módulo documents.py. Não foi executado pypdf real neste incremento.

O limite é de bytes de entrada, com overhead dos buffers Python. Não é um teto
de memória/CPU de todo o processo: PDF pode descomprimir para um volume maior e
o parser ainda não corre num processo isolado com quotas. A leitura não resolve
trocas hostis de caminhos entre validação e abertura nem garante snapshot coerente
se outro processo modificar bytes do mesmo ficheiro. Não usar árvores alteradas
em simultâneo para dados de clientes.

Referência primária consultada em 16/10/2026:
[Python 3.12 BufferedReader.read](https://docs.python.org/3.12/library/io.html#io.BufferedReader.read).
Sem novas dependências de produção.

Reproduzir os testes:
`py -3 -m unittest discover -s tests -p test_document_limits.py -v`.
