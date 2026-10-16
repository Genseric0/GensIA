# Painel local de diagnóstico — v0.32.0

Painel experimental, apenas de leitura, servido pela API existente em
`http://127.0.0.1:8765/panel`. HTML/CSS/JavaScript locais, sem framework, CDN,
analytics ou dependência de frontend. Mostra só metadados do diagnóstico: versão,
plataforma, modo de leitura, quotas configuradas/previstas e limitações.
Não é interface de chat/voz nem permite executar agentes, abrir ficheiros ou
consultar memória/modelos. **Fluxo em navegador real e layout ainda não validados.**

## Executar no computador local

Com o repositório atualizado e um ambiente virtual ativo, instalar apenas as
dependências opcionais da API se ainda não existirem:

```powershell
py -3 -m pip install -r requirements-api.txt
$env:GENSIA_API_TOKEN = py -3 -c "import secrets; print(secrets.token_hex(32))"
Write-Output $env:GENSIA_API_TOKEN
py -3 -m gensia.api
```

O token aparece apenas no teu terminal para poderes copiá-lo; não o partilhar,
fotografar ou versionar. Mantém esse terminal aberto. Numa janela normal do
navegador, escreve o endereço acima diretamente, introduz o token no campo e
escolhe **Consultar**. Não acrescentar token à URL, query, fragmento ou favoritos.
Se usares `--port`, escreve a porta correspondente. Só `127.0.0.1`, não localhost.
No Linux, usar `python` e `export GENSIA_API_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"`.
O comando de geração corre no teu computador quando o executares, não aqui.

Atualização manual. **Limpar sessão** apaga os dados mostrados, descarta a referência
ao token e cancela o pedido pendente. Recarregar a página exige novo token.
Ctrl+C termina o servidor. Para rotação, terminar, gerar outro token e reiniciar;
limpar sessão no painel não revoga o segredo do servidor.

## Fronteira de autenticação

- `/panel`, `/panel.css` e `/panel.js` são públicos **apenas como estrutura fixa**:
  não incluem token, metadados da instalação nem estado autenticado. Continuam
  sujeitos a Host exato, GET-only, ausência de query e guardas de origem/fetch.
- `/diagnostics` e as restantes rotas de dados continuam a exigir Bearer. Não há
  cookie de sessão ou login persistente. HTML não é gerado com dados privados.
- A única exceção nova de Origin é **GET /diagnostics**, com uma única origem
  `http://127.0.0.1:PORTA` exata e token válido. Origin null, alternativo, duplicado,
  de outra porta/protocolo e as outras rotas continuam recusados. Não adiciona CORS.
- Sec-Fetch-Site presente só aceita `same-origin` ou `none`, sem duplicados. Pedidos
  `cross-site`/`same-site` são recusados mesmo com token. Uma ligação aberta a partir
  de outro site pode ser recusada; escreve o endereço diretamente no navegador.
- CSP permite scripts/estilos/conexão apenas na mesma origem e favicon data:;
  proíbe scripts inline, framing, base e submissão de formulários. A CSP dos dados
  JSON não foi alargada. Há no-store, nosniff, no-referrer e CORP same-origin.
- Token só em memória JavaScript e no cabeçalho Authorization do pedido local.
  Sem localStorage/sessionStorage/cookies. Campo password limpo após utilização.
  Não é apagamento criptográfico da memória; navegador, extensões, autofill,
  histórico do terminal, clipboard e outro processo do mesmo utilizador podem
  observar o segredo. Usar perfil confiável, sem extensões suspeitas.
- Fetch GET fixo para /diagnostics, same-origin, credentials omit, cache no-store,
  redirect error, prazo 5s e máximo 64 KiB de resposta JSON. Falha limpa a sessão
  sem refletir o corpo de erro. Resposta tardia após limpar não volta a preencher
  os dados. Textos apresentados com textContent, nunca innerHTML.

O token único é uma credencial da instalação, não uma identidade por cliente.
HTTP apenas em loopback, não TLS; não expor esta API na Internet ou rede de clientes.
As limitações de documentos/quotas Windows e de isolamento mantêm-se.

## Validação de 16/10/2026

275 testes Python passaram sem omissões, incluindo oito novos: seis de guardas
do painel/API e dois via Uvicorn/HTTP real. A suite agora tem sete testes de socket
real. Servidor entregou assets sem token e recusou consultas de dados não autorizadas.
Novo teste de timeout PDF captura o Popen real, confirma SIGKILL e waitpid já
recolhido; substitui a antiga asserção indireta por ficheiro PID e existência em
/proc, que falhou numa execução. O comportamento de produção não foi alterado.

Dez testes Node/VM passaram: validação/limpeza do token, pedido fixo/sem persistência,
401, limite de resposta, schema, texto hostil sem HTML, limpeza/cancelamento,
resposta tardia, prazo e recusa de URL inadequada. DOM/fetch simulados: **não são
testes de layout, acessibilidade, motor do browser ou aplicação da CSP pelo browser**.
Bandit 1.9.4 em api.py/panel.py: 142 LOC, zero achados/erros. Não analisa JS/CSS.

```bash
GENSIA_TEST_REAL_HTTP=1 python -m unittest discover -s tests -v
node --test tests/panel.test.cjs
```

Playwright existente foi consultado sem instalar nada; Chromium não está disponível.
Não foram produzidas screenshots. [Registo da validação parcial](validation/2026-10-16-panel.json).
Antes de um piloto: navegador real com token válido/inválido, atualização, limpeza,
resposta tardia e rejeição de origem; inspeção CSP/rede/storage; teclado e ecrãs
1440/390/320 sem overflow. Capturas reais só depois dessa validação, sem token ou
dados de clientes. Não há alegação de instalação/execução no computador do utilizador.

Fontes primárias/documentação consultadas em 16/10/2026:
[Origin](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Origin),
[Fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch),
[CSP connect-src](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/connect-src).
Nenhuma dependência nova de produção; FastAPI/Starlette/Uvicorn já fixados.
