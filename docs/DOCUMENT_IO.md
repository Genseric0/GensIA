# Abertura de documentos por descritores — v0.30.0

Em POSIX com as primitivas necessárias, TXT/Markdown e a leitura interna de PDF
usam agora `document_io.read_confined`. Não há dependência nova: usa a biblioteca
padrão. Verificado em Linux/Python 3.12 em 16/10/2026; outros POSIX não testados.

## Proteções implementadas

- A pasta-base guarda a identidade `(st_dev, st_ino)` ao construir o leitor.
  Cada leitura abre a árvore absoluta componente a componente, a partir da raiz,
  e confirma a identidade da pasta-base. Não mantém descritores entre pedidos.
- Diretórios são abertos com `O_DIRECTORY | O_NOFOLLOW`, com nomes relativos ao
  descritor anterior. O ficheiro final usa `O_NOFOLLOW | O_NONBLOCK`. Não há uma
  nova resolução absoluta do caminho entre esses passos.
- `stat(..., follow_symlinks=False)` e `fstat` são comparados antes de ler.
  Só são aceites ficheiros regulares com um único hard link. Um hard link legítimo
  adicional passa a ser recusado neste modo; usar uma cópia própria do documento.
- A leitura pede no máximo limite+1 bytes. Identidade, modo, número de links,
  tamanho e timestamps de modificação/metadados são comparados depois. Alterações
  observadas ou tamanho incompatível com os bytes lidos recusam o resultado.
- Todos os descritores e streams são fechados em sucesso ou exceção. Um erro no
  caminho por descritores nunca provoca nova tentativa pelo caminho menos restrito.
- O pedido ao worker PDF inclui a identidade da pasta-base do pai; o worker
  compara-a antes de ler. Protege também essa passagem entre processos.

Uma subpasta renomeada **depois de aberta** continua a ser acedida pelo descritor
original; um symlink posto no seu nome não redireciona a leitura. O caminho relativo
devolvido é o rótulo pedido, não uma garantia de que esse nome ainda identifica o
mesmo ficheiro no fim. O hash refere-se aos bytes efetivamente devolvidos.

## Compatibilidade e limites

Em Windows e ambientes sem todas as primitivas necessárias conserva-se o caminho
anterior: validação por caminho e leitura limitada. **Não tem a proteção POSIX
contra trocas concorrentes.** Um teste simula essa seleção para compatibilidade;
não foi executado Windows real. Não usar pastas modificáveis por terceiros nem
considerar essa configuração aprovada para documentos de clientes.

Mesmo em POSIX isto não é uma sandbox nem um snapshot transacional. Timestamps
dependem do filesystem e não provam que nenhum byte mudou. Não protege contra
mounts hostis, alterações pelo administrador/kernel ou outro processo com as mesmas
permissões a manipular toda a instalação. Inicialização da pasta-base pressupõe um
ambiente confiável. O total de componentes da base e caminho é limitado a 128;
erros de permissões/recursos recusam a leitura. Outros ficheiros da aplicação,
como memória/auditoria, não passam automaticamente por este módulo.

As [quotas Linux do worker PDF](PDF_PROCESS.md) continuam independentes: a classe
SafePdfDocuments diretamente usa esta abertura, mas não recebe timeout/quotas.

## Evidência e reprodução

```bash
python -m unittest discover -s tests -p test_document_io.py -v
```

14 testes novos, com ficheiros temporários reais e trocas injetadas de forma
determinística: symlink final, subpasta trocada, diretório original ancorado após
rename, troca de ficheiro regular, FIFO entre stat/open, pasta-base substituída,
hard links, escrita in-place, crescimento limitado e ausência de fuga de descritores.
Incluem recusa antes do modelo/parser, identidade enviada ao worker e verificação
no worker com limites simulados (não altera quotas do processo de teste).
Casos POSIX são omitidos quando as primitivas não estão disponíveis; inspeção de
descritores via `/proc/self/fd` só onde existe. Os testes anteriores de crescimento
e erro de stream exercitam explicitamente o caminho de compatibilidade.

Suite completa: 255 testes passaram, zero omitidos, incluindo pypdf e HTTP reais.
Bandit 1.9.4 nos três módulos de produção alterados: um LOW B404 em subprocess,
zero MEDIUM/HIGH/erros. Não equivale a auditoria externa ou aprovação comercial.

Fontes primárias consultadas em 16/10/2026:
[Python 3.12 os.open/dir_fd](https://docs.python.org/3.12/library/os.html#os.open),
[fstat](https://docs.python.org/3.12/library/os.html#os.fstat),
[stat](https://docs.python.org/3.12/library/stat.html).
