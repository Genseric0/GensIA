# Extração PDF supervisionada — v0.27.0

Ativa o ambiente virtual e instala a dependência opcional, antes de executar:

```powershell
py -3 -m pip install -r requirements-documents.txt
py -3 -m gensia document --workspace . pdf-read-supervised exemplo.pdf --pdf-timeout 30
```

`exemplo.pdf` deve ser um ficheiro próprio existente dentro da pasta autorizada.
Aceita `--max-mib` (1–50, padrão 10), `--max-pages` (1–100, padrão 25) e
`--pdf-timeout` (1–120 segundos, padrão 30). Código 0 em sucesso, 8 em erro PDF.
Não envia texto ao modelo. Conteúdo extraído é apresentado no terminal em JSON;
o módulo mantém eventos locais de auditoria sem texto do documento.

Este comando acrescenta supervisão de processo. **pdf-read, pdf-summarize,
pdf-ask e pesquisa PDF continuam a usar o caminho anterior nesta versão.**

## Funcionamento e limites reais

O pai valida caminhos/limites, passa um pedido JSON ao worker próprio e aguarda
com timeout. O worker é iniciado no mesmo Python, em modo `-I -B`, com lista de
argumentos, `shell=False` e diretório temporário. Reutiliza SafePdfDocuments:
recusa traversal/symlinks, lê bytes limitados e verifica páginas/texto.
Resultados e erros do parser não são usados como comandos.

Em timeout, subprocess.run termina e recolhe o filho direto. O arranque inicial
do processo pode não ser interrompível em todas as plataformas; o timeout não
é garantia absoluta de tempo total. Não é feita gestão de uma árvore de processos.

A saída passa por ficheiro temporário e o pai lê até 2 MiB + 1 byte, validando
campos, tipos e limites. Stderr é descartado para não refletir logs do parser.
O ficheiro temporário é removido no fim, mas **não há quota de disco durante a
escrita**. O parser também não tem quota RAM/CPU do SO e pode consumir memória
antes do timeout. Saída temporária e ambiente herdado não constituem isolamento
de dados/credenciais: este processo tem as permissões do utilizador.

Não é sandbox de rede, ficheiros ou chamadas ao sistema. Não serve como garantia
para abrir PDFs hostis de clientes sem quotas e isolamento adicionais. Limites de
bytes de entrada e texto final não limitam toda a expansão interna do PDF.

## Dependência e evidência

`requirements-documents.txt`: pypdf==6.20.1, sem extras. Metadados primários
consultados em 16/10/2026 indicam Python>=3.9, BSD-3-Clause e publicação em
12/10/2026. Compatível com o requisito Python>=3.10 da GensIA e exercitado aqui
com Python 3.12/Linux. A versão fixa não substitui futura revisão de vulnerabilidades.

Nove testes em `tests/test_pdf_process.py`; suite completa com 225 testes passou,
sem omissões. Um PDF sintético real com texto foi gerado e extraído com pypdf
real, através da CLI/worker reais. PDF malformado foi recusado. Um processo Python
de teste bloqueado comprovou timeout e recolha do filho direto em Linux. Não é
um ensaio de PDF malicioso, resistência a OOM ou comportamento Windows.

Para reproduzir: `python -m unittest discover -s tests -p test_pdf_process.py -v`.
Os dois testes de pypdf são omitidos se a dependência estiver ausente; o teste de
existência do PID é específico de Linux. Testes simulados não são contados como
extração real. Nenhuma instalação foi feita no computador do utilizador.

Fontes primárias:
[subprocess.run](https://docs.python.org/3.12/library/subprocess.html#subprocess.run),
[pypdf 6.20.1 — metadados](https://pypi.org/project/pypdf/6.20.1/),
[changelog](https://pypdf.readthedocs.io/en/stable/meta/CHANGELOG.html).
