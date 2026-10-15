# Relatório visual offline — v0.22.0

O catálogo agora pode ser consultado num ficheiro HTML local, sem servidor,
JavaScript, token, CDN ou acesso à rede. Mostra os quatro agentes, capacidades,
dependências e limites. Não consulta o estado de execução nem verifica motores.
É um relatório estático, ainda não o painel interativo ligado à API.

## Gerar e abrir

Na raiz do repositório, com Python 3.10 ou superior (sem pacotes adicionais):

```powershell
py -3 -X utf8 -m gensia.catalog_report | Out-File -Encoding utf8 catalogo.html
Start-Process catalogo.html
```

Em Linux/macOS:

```bash
python3 -m gensia.catalog_report > catalogo.html
```

Depois abre `catalogo.html` no navegador. Estes comandos substituem um ficheiro
anterior com o mesmo nome; escolhe outro nome para conservar versões anteriores.
O relatório não se atualiza automaticamente. Para verificar dependências reais,
usa `python -m gensia.doctor --model NOME` separadamente.

## Validação e limites — 15/10/2026

- 152 testes passaram em Linux/Python 3.12, incluindo quatro novos testes.
- Verificados: quatro cartões, declarações de estado, escaping de metadados,
  ausência de elementos executáveis/remotos e equivalência CLI/renderizador.
- A importação não carrega executores, providers, ferramentas ou diagnósticos.
- CSS responsivo e de impressão incluído; inspeção visual em navegador pendente:
  a tentativa de Playwright falhou por ausência do executável Chromium.
- Sem novos motores/frameworks adotados. Usa apenas a biblioteca padrão Python.
- Não foi instalado ou executado no computador do utilizador.

Próximo passo: validar visualmente desktop/mobile e ligar um painel local de
leitura à API autenticada, mantendo as fronteiras de segurança existentes.
