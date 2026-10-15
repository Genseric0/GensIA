# Validação visual reproduzível

Ferramenta opcional de desenvolvimento; não é uma dependência do produto.
O relatório continua estático e não comprova agentes em execução.

## Execução local

Requer Node.js, Python da GensIA, pacote `playwright` e o Chromium correspondente.
A instalação é explícita e usa a rede; o script nunca instala nada por si próprio.
Seguir a [documentação oficial](https://playwright.dev/docs/library#usage),
consultada em 15/10/2026. Usar a CLI do mesmo pacote instalado para obter o browser.
Não usar um `npx` que descarregue outra versão sem querer.

Na raiz do repositório, depois de preparar essas dependências:

```sh
node --test tests/catalog_visual.test.cjs
node scripts/validate_catalog_visual.cjs capturas-novas
```

`GENSIA_PYTHON` pode indicar o executável Python (por exemplo `python` no Windows);
por omissão usa `python3`. A pasta de destino não pode existir. O script não
substitui evidências anteriores. Não publica nem envia ficheiros ao GitHub.

## O que verifica

- HTML produzido pelo código atual, não um mockup.
- Larguras 1440, 390 e 320 px; altura do viewport 900 px.
- Quatro cartões com dimensões positivas e sem corte horizontal.
- Aviso explícito de que não são agentes ativos e ausência de overflow horizontal.
- Contexto offline, service workers bloqueados e pedidos recusados.
- PNG full-page por largura e `validation.json`; código 1 em caso de falha.

`passed` significa apenas que estes critérios automáticos passaram. É necessário
abrir as imagens para avaliar legibilidade, sobreposições e aparência. Não é teste
completo de acessibilidade, comparação pixel-a-pixel nem teste em telemóvel real.
Imagens parciais podem existir se uma etapa posterior falhar; consultar sempre o JSON.

## Evidência de 15/10/2026

Quatro testes unitários dos critérios passaram. Integração tentou Playwright 1.62.1
mas não encontrou o executável Chromium. Uma tentativa de instalação separada
com `npx` resolveu 1.64.1 e recebeu um ZIP inválido; não foi concluída.
**Zero capturas HTML e nenhum resultado visual aprovado neste ambiente.**
As imagens existentes na galeria da CLI continuam a ser renderizações documentais.
