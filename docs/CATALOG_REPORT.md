# Relatório visual offline — v0.22.1

O catálogo agora pode ser consultado num ficheiro HTML local, sem servidor,
JavaScript, token, CDN ou acesso à rede. Mostra os quatro agentes, capacidades,
dependências e limites. Não consulta o estado de execução nem verifica motores.
É um relatório estático, ainda não o painel interativo ligado à API.

## Gerar e abrir

Na raiz do repositório, com Python 3.10 ou superior (sem pacotes adicionais):

```powershell
py -3 -m gensia.catalog_report --output catalogo.html
Start-Process catalogo.html
```

Em Linux/macOS:

```bash
python3 -m gensia.catalog_report --output catalogo.html
```

Depois abre `catalogo.html` no navegador. Se o destino já existir, o comando
recusa a escrita (código 13), mesmo que seja vazio ou uma ligação simbólica.
Escolhe outro nome. A criação é exclusiva, sem verificação separada antes de abrir.
Não cria pastas nem abre automaticamente o navegador. Usa UTF-8 explicitamente.
Falhas de pasta/permissões/espaço devolvem código 14; uma falha durante a escrita
pode deixar um novo ficheiro incompleto. Não há garantia contra alterações hostis
da pasta por outros processos. Sem `--output`, mantém a saída HTML no terminal;
redirecionamentos feitos pela shell não beneficiam desta proteção.
O relatório não se atualiza automaticamente. Para verificar dependências reais,
usa `python -m gensia.doctor --model NOME` separadamente.

## Validação e limites — 15/10/2026

- v0.22.1: 157 testes descobertos; 148 passaram e nove testes HTTP foram omitidos
  por falta das dependências opcionais da API no ambiente atual. Cinco novos testes
  cobrem UTF-8, destinos existentes, pastas ausentes, symlinks e CLI real repetida.
- Na v0.22.0, os 152 testes passaram com dependências opcionais instaladas.
- Verificados: quatro cartões, declarações de estado, escaping de metadados,
  ausência de elementos executáveis/remotos e equivalência CLI/renderizador.
- A importação não carrega executores, providers, ferramentas ou diagnósticos.
- CSS responsivo e de impressão incluído; inspeção visual em navegador pendente:
  a tentativa de Playwright falhou por ausência do executável Chromium.
- Sem novos motores/frameworks adotados. Usa apenas a biblioteca padrão Python.
- Não foi instalado ou executado no computador do utilizador.

Próximo passo: validar visualmente desktop/mobile e ligar um painel local de
leitura à API autenticada, mantendo as fronteiras de segurança existentes.
