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
Neste endpoint /agents/report, pedidos com Origin continuam recusados, mesmo para
a origem local; não há CORS. A exceção do painel só se aplica a GET /diagnostics.

## Proteções e validação

Mantém Host exato, Bearer obrigatório, apenas GET e ausência de query strings.
Resposta UTF-8, `no-store`, `nosniff`, `no-referrer` e disposição attachment.
Só a resposta HTML bem-sucedida permite CSS inline; scripts, rede, formulários e
embedding continuam bloqueados pela CSP. Respostas JSON mantêm a CSP anterior.
Três testes HTTP novos verificam conteúdo, cabeçalhos e rejeições.

Referência primária consultada em 15/10/2026:
[FastAPI HTMLResponse](https://fastapi.tiangolo.com/advanced/custom-response/).
Sem novas dependências de produção. Usa as versões já fixadas no projeto.

## Testar HTTP real (opcional)

Na raiz, com o ambiente virtual ativado e dependências API + `httpx` instaladas:

```powershell
$env:GENSIA_TEST_REAL_HTTP = "1"
python -m unittest discover -s tests -p test_api_socket.py -v
Remove-Item Env:GENSIA_TEST_REAL_HTTP
```

Para a suite completa, retirar `-p test_api_socket.py`. Sem esta variável, os
sete testes de socket são omitidos; os restantes testes continuam disponíveis.
Em Linux: `GENSIA_TEST_REAL_HTTP=1 python -m unittest discover -s tests -v`.

Os testes iniciam um servidor temporário em loopback numa porta efémera, reservada
antes do arranque, com token aleatório não impresso. Não precisam do teu token nem
de um servidor já em execução. Testam exportação e rejeições, incluindo cabeçalhos
Authorization/Host duplicados. O servidor e o socket são encerrados no fim.
Restrições locais que impeçam sockets provocam falha, não aprovação silenciosa.

Em 15/10/2026: 171 testes passaram em Linux com este opt-in. Não representa teste
de navegador, hardware, carga, TLS ou Windows. Esse incremento manteve v0.24.0.
Padrão de lifecycle baseado em [Uvicorn Config/Server](https://www.uvicorn.org/),
documentação oficial consultada na mesma data.

Na v0.31.0, `GET /diagnostics` inclui o [relatório de capacidades de proteção](PROTECTIONS.md).
O quinto teste de socket valida esse JSON, a recusa sem token e a ausência de
aprovação comercial/aplicação de quotas pelo diagnóstico. Mantém as mesmas guardas;
não há execução de documentos nem novos endpoints. 267 testes passaram no total
com o opt-in HTTP real em 16/10/2026.

Na v0.32.0, mais dois testes de socket validam os assets públicos do painel sem
dados/token e a exceção restrita de Origin em /diagnostics. Sete testes de socket
no total. O contrato autenticado de /agents/report não mudou; ver [painel](PANEL.md).
