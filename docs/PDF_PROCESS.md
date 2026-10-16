# Extração PDF supervisionada — v0.30.0

Ativa o ambiente virtual e instala a dependência opcional, antes de executar:

```powershell
py -3 -m pip install -r requirements-documents.txt
py -3 -m gensia document --workspace . pdf-read exemplo.pdf --pdf-timeout 30
```

`exemplo.pdf` deve ser um ficheiro próprio existente dentro da pasta autorizada.
Aceita `--max-mib` (1–50, padrão 10), `--max-pages` (1–100, padrão 25) e
`--pdf-timeout` (1–120 segundos, padrão 30). Código 0 em sucesso, 8 em erro PDF.
Não envia texto ao modelo. Conteúdo extraído é apresentado no terminal em JSON;
o módulo mantém eventos locais de auditoria sem texto do documento.

Desde a v0.28.0, `pdf-read`, `pdf-summarize`, `pdf-ask`, `search` e `ask-search`
usam a supervisão para PDFs por omissão. Cada comando aceita `--pdf-timeout`;
na pesquisa, o prazo é por PDF, não por lote. StudyAgent usa pesquisa supervisionada
com 30 segundos por PDF. O timeout de Ollama é independente deste prazo.
`pdf-read-supervised` permanece disponível por compatibilidade.

A classe SupervisedPdfDocuments é o adaptador recomendado em Python. Reutiliza
as regras de resumo e citações, devolvendo PdfDocument com os mesmos campos.
SafePdfDocuments é uma primitiva de baixo nível que ainda extrai no processo que
a chama; o worker usa essa primitiva. Chamadas diretas a ela não ganham timeout.
As quotas descritas abaixo também só são aplicadas pelo worker, não pela primitiva.
Não há fallback para extração direta quando o worker falha. Nessa situação,
resumo/perguntas/tutor não enviam conteúdo ao modelo.

## Funcionamento e limites reais

O pai valida caminhos/limites, passa um pedido JSON ao worker próprio e aguarda
com timeout. O worker é iniciado no mesmo Python, em modo `-I -B`, com lista de
argumentos, `shell=False` e diretório temporário. Reutiliza SafePdfDocuments:
recusa traversal/symlinks, lê bytes limitados e verifica páginas/texto.
Resultados e erros do parser não são usados como comandos.

Desde a v0.30.0, o pedido inclui a identidade da pasta-base validada pelo pai.
O worker recusa uma identidade diferente antes de ler o documento. Em POSIX com
suporte, o parser também usa [abertura por descritores](DOCUMENT_IO.md), sem seguir
symlinks e com verificação antes/depois da leitura; não é um snapshot transacional.

Em timeout, subprocess.run termina e recolhe o filho direto. O arranque inicial
do processo pode não ser interrompível em todas as plataformas; o timeout não
é garantia absoluta de tempo total. Não é feita gestão de uma árvore de processos.

A saída passa por ficheiro temporário e o pai lê até 2 MiB + 1 byte, validando
campos, tipos e limites. Stderr é descartado para não refletir logs do parser.
O ficheiro temporário é removido no fim. Desde a v0.29.0, o worker aplica limites
do kernel **apenas em Linux**, antes de ler o pedido e importar pypdf:

| Recurso | Teto configurado | Alcance |
| --- | --- | --- |
| Espaço de endereçamento, RLIMIT_AS | 512 MiB | Memória virtual do processo; não RAM reservada nem quota global |
| Tempo de CPU, RLIMIT_CPU | 30 segundos | CPU acumulada, independente do timeout de relógio |
| Tamanho de ficheiro, RLIMIT_FSIZE | 2 MiB | Por ficheiro escrito, incluindo stdout temporário; não total do disco |
| Core dump, RLIMIT_CORE | 0 bytes | Evita core dumps normais do worker |

Limites soft/hard herdados mais baixos são preservados. Cada aplicação é verificada
com getrlimit; falha de configuração em Linux interrompe a extração, sem fallback.
O pai valida o relatório de limites e o schema do documento antes de aceitar texto.
São dados do worker próprio e confiável, não uma atestação contra processos hostis.
Não se usa preexec_fn nem se alteram quotas do processo principal.

Fora de Linux, não se tenta aplicar estas quotas: conserva-se a supervisão anterior
com timeout, com resource_limits.applied=false e identificação da plataforma.
`pdf-read-supervised` inclui esse relatório no JSON; os restantes pipelines mantêm
o formato anterior de documento. Não há opção para desativar quotas em Linux.
Ficheiros legítimos que excedam os limites podem falhar; não se aumenta o teto
automaticamente. Outros Unix e Windows continuam sem quotas nesta implementação.

A auditoria do parser usa um ficheiro privado dentro da pasta temporária. O pai
regista read_pdf_process success/error/timeout no log configurado; o log existente
não fica sujeito ao limite do filho. Falha de recursos e erro do parser partilham
mensagem genérica: não se infere uma causa exata a partir do código de saída.
Saída temporária e ambiente herdado não constituem isolamento de dados/credenciais:
este processo continua com as permissões do utilizador.

Não é sandbox de rede, ficheiros ou chamadas ao sistema. Não serve como garantia
para abrir PDFs hostis de clientes sem isolamento adicional. Não há quota agregada
de disco/processos descendentes, gestão de árvore de processos ou isolamento de
rede. Os limites Linux reduzem consumo por processo, não tornam o parser inviolável.

## Dependência e evidência

`requirements-documents.txt`: pypdf==6.20.1, sem extras. Metadados primários
consultados em 16/10/2026 indicam Python>=3.9, BSD-3-Clause e publicação em
12/10/2026. Compatível com o requisito Python>=3.10 da GensIA e exercitado aqui
com Python 3.12/Linux. A versão fixa não substitui futura revisão de vulnerabilidades.

Nove testes em `tests/test_pdf_process.py`; na v0.27.0 a suite com 225 testes passou,
sem omissões. Um PDF sintético real com texto foi gerado e extraído com pypdf
real, através da CLI/worker reais. PDF malformado foi recusado. Um processo Python
de teste bloqueado comprovou timeout e recolha do filho direto em Linux. Não é
um ensaio de PDF malicioso, resistência a OOM ou comportamento Windows.

Na v0.28.0 foram acrescentados sete testes em `tests/test_pdf_pipeline.py` e os
232 testes passaram sem omissões. CLI de leitura e pesquisa exercitadas com PDF e
worker reais. Resumo/perguntas/tutor usam fixtures de extração/modelo nos testes de
encaminhamento, citações e falha antes do provider; não houve inferência real nova.

Para reproduzir: `python -m unittest discover -s tests -p test_pdf_process.py -v`.
Os dois testes de pypdf são omitidos se a dependência estiver ausente; o teste de
existência do PID é específico de Linux. Testes simulados não são contados como
extração real. Nenhuma instalação foi feita no computador do utilizador.

Na v0.29.0, nove testes novos em test_pdf_limits.py cobrem limites herdados,
plataforma não suportada simulada, relatórios inválidos, falha antes do parser e
confirmação do kernel. Em Linux, processos reais demonstraram recusa de alocação
de 1 GiB, recusa de escrita acima de 2 MiB e encerramento por CPU (teto reduzido
a 1 segundo só nesse filho de teste). Os limites do pai ficaram inalterados.
Após falha real de recursos num filho sintético, o pedido seguinte extraiu um PDF
real com pypdf, mesmo com log do pai maior que 2 MiB. Não é ensaio com PDF-bomba
nem validação Windows. Ver VALIDATION.txt para a suite completa.

Reproduzir quotas: `python -m unittest discover -s tests -p test_pdf_limits.py -v`.
Os casos reais específicos de Linux/pypdf são omitidos quando indisponíveis.

Fontes primárias:
[subprocess.run](https://docs.python.org/3.12/library/subprocess.html#subprocess.run),
[resource/setrlimit — Python 3.12](https://docs.python.org/3.12/library/resource.html)
(consultada em 16/10/2026; módulo padrão, sem nova dependência),
[pypdf 6.20.1 — metadados](https://pypi.org/project/pypdf/6.20.1/),
[changelog](https://pypdf.readthedocs.io/en/stable/meta/CHANGELOG.html).
