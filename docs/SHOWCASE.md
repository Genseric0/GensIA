# GensIA — apresentação técnica

Estado documentado em 14 de outubro de 2026, versão 0.21.0.

## Objetivo

Construir um assistente pessoal modular que trabalhe com modelos locais, documentos,
voz e ferramentas explícitas do sistema, com controlo sobre permissões e dados.
O projeto está em fase de protótipo. A interface atual é CLI + API local;
não existe ainda um dashboard nem agentes permanentemente ativos.

## Galeria da interface atual

As imagens são renderizações SVG do stdout/stderr de comandos reais executados
num ambiente Linux de desenvolvimento. Não são mockups nem screenshots de uma GUI.
Os exemplos usam apenas dados sintéticos, sem documentos pessoais, chaves ou tokens.

### Terminal
![Terminal](screenshots/01-terminal.svg)
[Saída original](screenshots/01-terminal.txt). Mostra os comandos efetivamente disponíveis.

### Agentes especializados
![Agentes](screenshots/02-agentes.svg)
[Saída original](screenshots/02-agentes.txt). Coordenador, segurança, revisor e tutor.
Listar agentes não os executa. A delegação é limitada e sequencial.

### Segurança
![Segurança](screenshots/03-seguranca.svg)
[Saída original](screenshots/03-seguranca.txt). Análise sintática passiva de um URL
de exemplo, sem o visitar. Não constitui diagnóstico de malware ou reputação.

### Memória
![Memória](screenshots/04-memoria.svg)
[Saída original](screenshots/04-memoria.txt). Escrita e consulta explícitas em SQLite;
a base temporária da demonstração é eliminada no final.

### Documentos
![Documentos](screenshots/05-documentos.svg)
[Saída original](screenshots/05-documentos.txt). Pesquisa lexical sobre texto sintético
de redes. Esta demonstração não utiliza um LLM.

## O que foi construído

| Área | Implementação | Limite atual |
| --- | --- | --- |
| Núcleo | CLI modular e contrato de provider | Modelo local configurado separadamente |
| Ollama | Adaptador local, sem proxies/redirecionamentos | API real validada; inferência real pendente |
| Sistema | Listagem confinada, aplicações permitidas e auditoria | Não é uma sandbox de SO; Windows por validar |
| Memória | SQLite, guardar/consultar/apagar explícitos | Sem aprendizagem automática de preferências |
| Voz | Whisper, Piper e gravação limitada | Motores e hardware reais ainda por validar |
| Documentos | TXT/Markdown/PDF, pesquisa e respostas com referências | PDF/LLM opcionais; referências não provam veracidade |
| Segurança | Análise passiva, Bandit, CISA KEV e VirusTotal opt-in | Sem garantia de deteção; serviços externos exigem autorização |
| Agentes | Coordenador, segurança, revisor e tutor | Sem execução de comandos livres pelo modelo |
| API e painel | Estado, diagnóstico, catálogo e painel experimental em /panel | Loopback, dados com token, apenas leitura; browser/layout reais pendentes |

## Evidências de engenharia

Na validação da v0.21.0: **148 testes passaram**, incluindo testes HTTP opcionais.
Bandit real analisou 17 módulos com três avisos baixos B404 e nenhum médio/alto.
Uvicorn real confirmou respostas 200 autorizadas, 401 sem token e 405 para POST.
Estes resultados não equivalem a certificação de segurança nem validação em produção.

Na v0.32.0: 275 testes Python passaram, incluindo sete HTTP reais, e dez testes
Node/VM do painel. Não são validação de navegador, layout ou CSP real. Chromium
ausente no ambiente; não há screenshots do painel. As imagens desta galeria
continuam a ser renderizações documentais de saídas CLI, não capturas da GUI.

- [Arquitetura e fronteiras de confiança](ARCHITECTURE.md)
- [Utilização e instalação](USAGE.md)
- [Equipa de agentes](AGENT_TEAM.md)
- [Integração real com motores](REAL_ENGINE_VALIDATION.md)
- [Catálogo autenticado da API](AGENT_CATALOG_API.md)
- [Painel experimental, autenticação e validação pendente](PANEL.md)
- [Histórico completo de progresso](../PROGRESS.md)
- [Registo de validações](../VALIDATION.txt)

## Reproduzir a galeria

Na raiz do repositório, com Python 3.10 ou superior:

```bash
python scripts/capture_showcase.py
```

O script executa cinco demonstrações reais, preserva as saídas em `.txt` e gera
as imagens SVG. Usa a biblioteca padrão e uma pasta temporária; não faz pedidos
à rede nem altera ficheiros pessoais. Datas de notas podem mudar entre execuções.

## Próximos passos

Validar o painel de diagnóstico em navegador real, produzir capturas sem segredos
e validar inferência com pesos Ollama locais. Depois, ampliar voz e Windows. Não há promessa de que os
adaptadores existentes estejam já validados em todos os sistemas e equipamentos.
