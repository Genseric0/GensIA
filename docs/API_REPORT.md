# Exportação autenticada do catálogo — v0.24.0

`GET /agents/report` devolve o relatório HTML como anexo `gensia-agents.html`.
Reutiliza o gerador offline: catálogo estático, não estado de agentes em execução.
Não lê memória, documentos ou modelos. Não é ainda um painel interativo.

## Executar localmente

Com as dependências de `requirements-api.txt` instaladas num ambiente virtual,
define `GENSIA_API_TOKEN` com um segredo aleatório alfanumérico de 32–256 caracteres
e inicia `python -m gensia.api`. Consulta o guia da API para a configuração completa.
O serviço escuta apenas em `127.0.0.1:8765`.

Num segundo terminal PowerShell, com o mesmo token definido no ambiente:

```powershell
$headers = @{ Authorization = "Bearer $env:GENSIA_API_TOKEN" }
$report = Invoke-WebRequest -Uri http://127.0.0.1:8765/agents/report -Headers $headers
$report.StatusCode
```

Este exemplo consulta em memória, sem substituir ficheiros. Para criar um ficheiro
local com proteção contra substituição, continua a usar:

```powershell
py -3 -m gensia.catalog_report --output catalogo-novo.html
Start-Process catalogo-novo.html
```

Não colocar o token na URL, código, imagens ou repositório. Abrir simplesmente a
URL no navegador não autentica: resulta em 401. Não existe cookie ou página de login.
Pedidos com Origin continuam recusados, mesmo para a origem local; não há CORS.

## Proteções e validação

Mantém Host exato, Bearer obrigatório, apenas GET e ausência de query strings.
Resposta UTF-8, `no-store`, `nosniff`, `no-referrer` e disposição attachment.
Só a resposta HTML bem-sucedida permite CSS inline; scripts, rede, formulários e
embedding continuam bloqueados pela CSP. Respostas JSON mantêm a CSP anterior.
Três testes HTTP novos verificam conteúdo, cabeçalhos e rejeições.

Referência primária consultada em 15/10/2026:
[FastAPI HTMLResponse](https://fastapi.tiangolo.com/advanced/custom-response/).
Sem novas dependências de produção. Usa as versões já fixadas no projeto.
