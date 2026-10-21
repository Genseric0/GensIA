# Interface de conversa — candidata 0.61

A página `/app` conversa com o modelo Ollama local configurado no arranque da API.
`/panel` mantém o diagnóstico técnico. O backend utiliza o mesmo provider da CLI.

## Arranque local

Instalar a GensIA com o extra API num ambiente virtual. Preparar previamente um
modelo local no Ollama e desativar a cloud no servidor (`OLLAMA_NO_CLOUD=1`, seguido
de reinício). A GensIA verifica `/api/show` antes da geração e recusa modelos
remotos ou cuja localidade não possa confirmar. Não descarrega modelos.

```powershell
.\.venv\Scripts\python.exe -m gensia.api --chat-model NOME_DO_MODELO_LOCAL --ephemeral-token
```

Em Linux/macOS, usar `.venv/bin/python` no comando equivalente. Abrir
`http://127.0.0.1:8765/app` e introduzir o token dessa execução. A porta é reservada
antes da apresentação do token; uma porta ocupada falha sem o revelar.

Para um token persistente, exportar `GENSIA_API_TOKEN` com 32–256 caracteres ASCII
alfanuméricos aleatórios e omitir `--ephemeral-token`. O ficheiro `.env` não é
carregado automaticamente. Sem `--chat-model`, a página explica a configuração.

## Fluxo disponível

- Verificar manualmente metadados do modelo antes de conversar. Esta consulta não
  realiza inferência e não envia o histórico.
- Mensagens do utilizador até 4.000 caracteres e respostas até 8.000 caracteres.
  O contexto contém até quatro pares e uma nova mensagem, limitado a 12.000
  caracteres e 32 KiB de JSON. A página remove pares antigos completos quando
  necessário, incluindo quando caracteres Unicode excedem o limite em bytes.
- Nova conversa limpa o contexto da página. Terminar sessão limpa token e mensagens.
- Cancelar espera aborta a espera no navegador. Um worker no servidor pode continuar
  e mantém a exclusão até terminar. Respostas tardias não voltam à página.
- Token e histórico ficam em memória, sem cookies, localStorage ou sessionStorage.
  A sessão da página expira após cinco minutos de inatividade e ao sair da página.
  Isto não revoga a credencial do servidor. Terminar o processo revoga o token efémero.

Há uma inferência por aplicação de cada vez, com resposta 429 quando ocupada.
Esse limite não é um rate limit por janela de tempo. A API escuta exclusivamente
em `127.0.0.1`, valida Host e Origin, não permite CORS, limita JSON e devolve erros
fixos. A CSP não depende de CDN. Texto do modelo é apresentado com `textContent`.

A conversa não executa ferramentas, não envia emails e não acede automaticamente
a notas ou documentos. As ferramentas existentes continuam explícitas na CLI.
O limite do campo de texto no navegador conta unidades UTF-16; caracteres fora do
BMP, incluindo alguns emojis, podem atingir o limite mais cedo que no backend.

## Validação executada em 21/10/2026

| Comando | Resultado | Alcance |
| --- | --- | --- |
| `.venv/bin/python -B -m unittest discover -s tests -p test_chat.py -q` | 16 aprovados | Contrato e API em processo com provider sintético |
| `.venv/bin/python -B -m unittest discover -s tests -p test_api.py -q` | 14 aprovados | Regressão da API e launcher |
| `node --test tests/chat.test.cjs` | 10 aprovados | Fluxos do JavaScript com fixture DOM, sem layout real |
| `node --check gensia/web/app.js` | Aprovado | Sintaxe do JavaScript |
| `node --check scripts/validate_chat_browser.cjs` | Aprovado | Sintaxe do runner |
| Servidor QA em subprocesso com HTTP loopback real | Aprovado | Health, metadados, conversa e continuidade com provider sintético |

Os testes cobrem Unicode, continuidade com respostas de 4.001 e 8.000 caracteres,
recusa de 8.001 caracteres, contexto, roles, JSON duplicado, autenticação, origens,
concorrência, modelos remotos, respostas inválidas, erros sem dados privados,
assets e delegação ao listener que reserva a porta. O JavaScript também verifica
remoção de pares por limite de bytes, cancelamento, resposta tardia, sessão
expirada, limpeza e apresentação de HTML como texto. O TestClient apresenta um
aviso de depreciação do adaptador httpx; os testes listados foram efetivamente executados.

## Navegador e capturas

`scripts/validate_chat_browser.cjs` abre a aplicação real num servidor loopback com
um provider explicitamente sintético. Testa ligação, contexto, HTML como texto,
erros, cancelamento, nova conversa, limpeza, token recusado e larguras
1.440, 768, 390 e 320 pixels. Captura PNG do navegador apenas após os passos de
ligação e conversa. As respostas nas capturas são identificadas como
`TESTE SINTÉTICO`; uma captura não comprova inferência com pesos reais.

```bash
GENSIA_PYTHON=.venv/bin/python node scripts/validate_chat_browser.cjs --output artifacts/chat-browser
```

O diretório de saída deve ainda não existir. O Node precisa de Playwright e de
Chromium disponíveis. É possível resolver Playwright através de `NODE_PATH` ou
`CODEX_PRIMARY_RUNTIME_NODE_MODULES`. O runner só retorna código 0 quando todos os
fluxos passam; código 2 indica bloqueio ou falha. `validation.json` regista os
passos concluídos, as capturas efetivamente criadas e o motivo do bloqueio.

Nesta execução, Playwright 1.62.1 está presente, mas o download do Chromium
terminou com ZIP truncado. O E2E visual está **BLOCKED**. Não foi criada nenhuma
captura nesta tentativa; `docs/screenshots/chat-browser-2026-10-21/validation.json`
regista `chromium_unavailable`. O workflow de navegador poderá executar o mesmo
runner quando o browser estiver disponível; o seu resultado deve ser consultado.

Inferência com pesos reais, instalação em Windows e áudio real continuam por
validar. Esta interface local não constitui uma plataforma comercial multiutilizador.
# Evidência posterior no CI — 21/10/2026

O job Chromium118961545502 passou no commit18a87ae. O artifact foi descarregado,
o hash verificado e as quatro imagens inspecionadas. Ver
[capturas e proveniência](screenshots/ci-39520092421/README.md). Esta evidência
fecha o percurso E2E sintético do runner em desktop/tablet/telemóvel. A limitação
de Chromium local abaixo continua verdadeira; não impede a evidência remota.
Inferência com pesos reais e acessibilidade completa permanecem por validar.

