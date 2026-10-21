# Dependências e auditoria do ambiente

Verificação em 21/10/2026, na venv Linux com Python 3.12.14. A tabela regista
metadados das distribuições efetivamente instaladas; não representa um lock
completo, uma declaração de versão mais recente ou uma aprovação jurídica.
O núcleo da GensIA continua sem dependências obrigatórias de terceiros.

| Distribuição | Versão instalada | Licença declarada | Python mínimo declarado |
| --- | --- | --- | --- |
| pip | 26.2.1 | MIT | 3.10 |
| setuptools | 84.0.0 | MIT | 3.10 |
| wheel | 0.48.0 | MIT | 3.9 |
| build | 1.6.1 | MIT | 3.10 |
| FastAPI | 0.143.0 | MIT | 3.10 |
| Uvicorn | 0.54.0 | BSD-3-Clause | 3.10 |
| Starlette, transitiva | 1.9.0 | BSD-3-Clause | 3.11 |
| Pydantic, transitiva | 2.14.1 | MIT | 3.10 |
| httpx | 0.28.1 | BSD-3-Clause | 3.8 |
| pypdf | 6.20.1 | BSD-3-Clause | 3.9 |
| Bandit | 1.9.4 | Apache-2.0 | 3.10 |
| coverage | 7.16.2 | Apache-2.0 | 3.10 |
| pip-audit | 2.10.1 | Apache Software License | 3.10 |

Fontes primárias consultadas para os pins de runtime e a correção do instalador:
[pip 26.2.1](https://pypi.org/project/pip/26.2.1/),
[FastAPI 0.143.0](https://pypi.org/project/fastapi/0.143.0/),
[Uvicorn 0.54.0](https://pypi.org/project/uvicorn/0.54.0/),
[pypdf 6.20.1](https://pypi.org/project/pypdf/6.20.1/).
As versões existentes de API/PDF foram preservadas. Não foram adotadas alegações
de desempenho dos fornecedores nem instaladas outras stacks de agentes.

## Compatibilidade e resolução

O projeto declara Python >=3.10 para o núcleo. O ambiente com API e PDF foi
executado em Python 3.12; o CI exige 3.12 e 3.13 em Linux e Windows. A Starlette
1.9.0 resolvida neste ambiente exige Python >=3.11. Uma instalação API em 3.10
pode resolver outras transitivas e não está validada por estes resultados.
Os testes Windows/3.13 dependem dos resultados reais do CI, sem os inferir de
uma execução Linux/3.12.

Atualização: o [run39521033113](https://github.com/Genseric0/GensIA/actions/runs/39521033113)
passou em Linux/Windows com Python3.12/3.13, incluindo instalação, testes e wheel.
Ver TEST_REPORT.md para as omissões específicas de plataforma. Esta evidência
não amplia automaticamente a matriz suportada para Python3.10/3.11 ou macOS.

`requirements-dev.txt` e os extras fixam dependências diretas. Não fixam todos os
pacotes transitivos nem usam hashes; futuras resoluções podem diferir. Antes de
distribuir a clientes, repetir a instalação, `pip check`, a auditoria e os testes
na plataforma suportada. A licença do próprio projeto deve ser definida pelo
titular antes de distribuição comercial; as licenças dos componentes não a
substituem. Modelos e respetivos pesos exigem avaliação própria.

## Vulnerabilidades observadas e correção

A primeira auditoria encontrou 12 entradas de advisory no pip 25.0.1, referentes
a seis identificadores únicos: CVE-2025-8869, CVE-2026-1703, CVE-2026-3219,
CVE-2026-6357, CVE-2026-8643 e CVE-2026-13346. Nenhum outro pacote instalado
teve achados nessa execução. Atualizámos e fixámos o instalador em pip 26.2.1.
Não foi necessário alterar dependências de runtime para corrigir estes achados.

Validação efetivamente executada depois da atualização:

```bash
.venv/bin/python -m pip check
.venv/bin/python -m pip_audit --local --strict --progress-spinner off --format json --output artifacts/dependencies.json
```

Ambos terminaram com código 0. O relatório final contém 52 distribuições e zero
advisories conhecidos. Esse relatório inclui apenas distribuições publicadas.
Na execução remota com a GensIA instalada em editable, a consulta direta em modo
strict falhou por a distribuição `gensia-local` não estar publicada; `--skip-editable`
também não resolveu a reprodução. O CI usa o inventário completo das restantes
distribuições, sem voltar a resolver dependências:

```bash
.venv/bin/python -m pip freeze --all --exclude-editable > artifacts/audit-requirements.txt
.venv/bin/python -m pip_audit --strict --disable-pip --no-deps -r artifacts/audit-requirements.txt --progress-spinner off --format json --output artifacts/dependencies.json
```

O workflow exige primeiro que `gensia-local` seja a única distribuição editable.
Se aparecer outra, a auditoria falha antes da exclusão. `freeze --all` inclui os
build tools e todas as transitivas; `--no-deps` não os omite deste inventário.
O código da própria GensIA é analisado por Bandit, revisão e testes, não por uma
pesquisa de uma publicação PyPI inexistente. A reprodução local com o inventário
terminou com código 0 e zero advisories; o CI repete no seu próprio ambiente.
O modo `--strict` trata indisponibilidade ou dados insuficientes como erro; um
relatório sem alertas não comprova ausência de vulnerabilidades desconhecidas.

## Navegador e cadeia de fornecimento do CI

O job visual instala Playwright 1.62.1 num prefixo isolado em `artifacts/browser`
com scripts npm desativados e instala explicitamente o Chromium correspondente.
É uma dependência de testes, não do pacote Python nem do computador do cliente.
Não existe lock npm transitivo desta ferramenta isolada; esta limitação deve ser
considerada ao reproduzir a execução. O pip-audit cobre o ambiente Python, não o
Chromium ou a árvore npm. Actions são fixadas por SHA, com token somente de
leitura, sem credenciais persistidas, produção ou secrets de aplicação.
