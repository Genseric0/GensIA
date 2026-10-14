# Validação real — 14/10/2026

Base: commit `6d47f609890f8dcc87853442fa2663dff2e5a993`, com a correção de
transporte da v0.19.1. Ambiente Linux/Python 3.12; nenhuma instalação no PC do
utilizador. [Evidências JSON](validation/2026-10-14-real-engines.json) incluem
hashes do código analisado, achados e verificações realizadas.

| Verificação | Resultado observado |
| --- | --- |
| Testes da aplicação | 131 passaram |
| Bandit 1.9.4 sobre `gensia/` | 15 ficheiros, 3 LOW B404, 0 MEDIUM/HIGH, scan completo |
| Fixture com `shell=True` | B602 HIGH detetado, conteúdo não executado, bytes preservados |
| HTTP redirects 301/302/303/307/308 | Recusados antes de visitar o destino |
| Proxy configurado por ambiente | Não recebeu o pedido do provider |
| Ollama 0.40.4 real | Arranque CPU, `/api/version` e `/api/tags` funcionaram |
| Modelo ausente | `ProviderUnavailable`, sem fallback |
| Geração de respostas | Não validada: download do modelo bloqueado |

O scan anterior assinalou B310 MEDIUM em `urlopen`. A revisão encontrou que
redirecionamentos e proxies podiam alterar o destino da ligação local. A correção
usa um opener próprio sem proxies e bloqueia redirects. A evidência principal são
os testes HTTP reais, não apenas o desaparecimento do alerta estático.

Os três B404 restantes são importações de `subprocess` em `static_analysis.py`,
`tools.py` e `voice.py`; merecem revisão contínua, não foram suprimidos. Ausência
de achados médios/altos não é uma garantia de segurança nem uma auditoria completa.

## Limitação do Ollama

O binário oficial 0.40.4 foi verificado com SHA-256
`15f31e9576d15a481e099b4145dba6e9f8c1f295927d6b8895300ae30ed3740a`.
O servidor foi iniciado temporariamente em loopback com `OLLAMA_NO_CLOUD=1`.
O download de `qwen2.5:0.5b` falhou na resolução DNS do armazenamento para onde
o pedido foi redirecionado. Não se contornou a restrição de rede.
Sem pesos, foi possível testar a API e o erro de modelo ausente, mas não o
revisor/tutor com geração real. Todos os servidores lançados foram encerrados.

## Reproduzir no Windows

Na pasta do repositório, com Python instalado:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install bandit==1.9.4
.\.venv\Scripts\python.exe -m gensia.agents audit --workspace . --code gensia
```

Com Ollama instalado, iniciar num terminal separado (encerrar antes outra
instância que já esteja a ocupar a porta):

```powershell
$env:OLLAMA_NO_CLOUD="1"
ollama serve
```

No terminal do projeto, descarregar o modelo de teste e executar o roteiro:

```powershell
ollama pull qwen2.5:0.5b
.\.venv\Scripts\python.exe scripts/validate_agents_real.py --model qwen2.5:0.5b
```

O roteiro usa apenas ficheiros sintéticos temporários e motores reais. Verifica
Bandit, integridade da fixture, resposta do revisor e referência do tutor. Sai
com código 1 se faltar uma dependência/modelo ou alguma verificação falhar.
Não instala, descarrega ou inicia serviços automaticamente. O modelo pequeno é
apenas candidato para teste de integração, não uma avaliação de qualidade geral.

Para repetir a suite completa, instalar também `requirements-api.txt` e o cliente
de testes `httpx`, e executar `python -m unittest discover -s tests -v`.
O TestClient atual emite um aviso de depreciação sobre httpx; não impediu os testes.
Sem API, seis testes HTTP são omitidos.

## Fontes primárias consultadas

- [Bandit 1.9.4](https://pypi.org/project/bandit/1.9.4/): release de 25/02/2026,
  Python >=3.10, Apache-2.0; instalação real compatível com Python 3.12.
- [Ollama 0.40.4](https://github.com/ollama/ollama/releases/tag/v0.40.4): release
  de 12/10/2026; binário Linux amd64 e digest oficiais.
- [Licença Ollama](https://github.com/ollama/ollama/blob/v0.40.4/LICENSE): MIT.
- [Instalação Linux](https://docs.ollama.com/linux).
- [Qwen2.5 0.5B](https://ollama.com/library/qwen2.5:0.5b): candidato de cerca de
  398 MB, Apache-2.0; sem pesos instalados neste teste, sem benchmark adotado.

Próximo passo: executar o roteiro com pesos locais disponíveis e avaliar as
respostas antes de integrar os relatórios no painel.
