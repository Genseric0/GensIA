# Catálogo dos agentes na API — v0.21.0

`GET /agents` fornece metadados estáticos dos quatro agentes existentes. É a base
de consulta para uma futura interface gráfica, não uma rota de execução nem um
monitor de processos. O catálogo e `python -m gensia.agents list` partilham a
mesma definição em `gensia/agent_catalog.py`.

## Executar localmente

Na pasta do projeto, preparar a API opcional:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
$env:GENSIA_API_TOKEN = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.\.venv\Scripts\python.exe -m gensia.api
```

Guardar o token de forma privada antes de iniciar o servidor. Num segundo terminal
PowerShell, introduzir o mesmo token sem o colocar no histórico do comando:

```powershell
$secret = Read-Host "Token desta instância GensIA" -AsSecureString
$credential = New-Object System.Management.Automation.PSCredential("token", $secret)
$token = $credential.GetNetworkCredential().Password
Invoke-RestMethod http://127.0.0.1:8765/agents -Headers @{Authorization="Bearer $token"}
Remove-Variable token, credential, secret
```

Este método mantém o token em memória durante o pedido; não o colocar no Git,
URL ou relatórios. Encerrar o servidor com Ctrl+C. A API só escuta em loopback.

## Contrato

| Campo | Valor/significado |
| --- | --- |
| `schema_version` | `1`, versão do contrato do catálogo |
| `kind` | `static_capabilities`, informação declarada no código |
| `runtime_state` | `not_observed`, não foi observado nenhum estado de execução |
| `execution_exposed` | `false`, não oferece execução pela API |
| `dependencies_checked` | `false`, não verifica instalações ou modelos |
| `agents` | Quatro descrições com IDs, capacidades, dependências e limites |

IDs: `coordinator`, `security`, `reviewer`, `study`. Cada capacidade tem `id`,
`dependencies`, `model_use` (`none`, `optional` ou `required`) e `limits`.
Dependências condicionais usam nomes explícitos, como `pypdf_if_pdf`.
Estes campos não concedem permissões nem provam que uma tarefa pode executar agora.
Para verificar o ambiente usar `gensia.doctor`; para inferência real usar o roteiro
de integração. A listagem não inicia nenhum desses diagnósticos.

## Limites de segurança

- Exige `Authorization: Bearer TOKEN` e Host exato `127.0.0.1:PORTA`.
- Rejeita cabeçalho Origin, query strings e métodos diferentes de GET.
- Não existe `/agents/run`, acesso a ficheiros, prompts, relatórios pessoais ou logs.
- Não importa o executor de agentes, providers ou ferramentas para servir o catálogo.
- Usa contrato de resposta tipado para excluir campos não declarados.
- Mantém `Cache-Control: no-store`, `nosniff` e política CSP restritiva.

A API não foi aberta a navegadores nesta etapa: não há CORS nem painel servido.
Processos locais comprometidos ficam fora do modelo de ameaça. Não publicar a
porta através de proxies, túneis ou na Internet.

## Verificação em 14/10/2026

148 testes passaram, sete novos: IDs e compatibilidade CLI, cópias independentes,
dependências declaradas, importação isolada da API, resposta HTTP, proteções da
rota e exclusão de campos extra. Nove testes HTTP são omitidos sem API/httpx.

Um processo Uvicorn real em loopback devolveu HTTP 200 com quatro agentes,
`runtime_state=not_observed` e `no-store`; sem token devolveu 401 e POST devolveu
405. O processo foi encerrado no fim. Não houve teste num navegador real.
Bandit 1.9.4 real: 17 módulos, três B404 LOW, zero MEDIUM/HIGH; não é garantia de
segurança. Nada foi instalado no computador do utilizador.

Referência primária consultada em 14/10/2026:
[FastAPI — Response Model](https://fastapi.tiangolo.com/tutorial/response-model/).
Reutilizadas as dependências existentes; nenhuma biblioteca nova adotada.
