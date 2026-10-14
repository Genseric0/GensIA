# Equipa local — v0.19.0

Implementação em `gensia/agents.py`, reutilizando os módulos existentes. Nenhum
framework de swarm ou dependência adicional obrigatória foi introduzido.

| Agente | Trabalho | Motor |
| --- | --- | --- |
| coordinator | Valida alvos, delega, mantém resultados parciais | Regras determinísticas |
| security | Analisa sintaxe de URLs e código Python | Analisador passivo e Bandit opcional |
| reviewer | Ordena achados de código por severidade e reúne evidências | Regras; Ollama opcional para recomendações |
| study | Recupera trechos de documentos indicados e responde com referências | Pesquisa lexical e Ollama local |

São agentes especializados com coordenação sequencial limitada. Não são processos
permanentes nem agentes com liberdade de executar comandos. O coordenador não usa
um modelo para decidir ferramentas. O GitHub guarda o código; executá-lo requer
Python no computador onde se pretende trabalhar.

## Executar

Na pasta do repositório, Windows/Python 3.10+:

```powershell
py -3 -m gensia.agents list
py -3 -m gensia.agents audit --workspace . --url https://example.com
```

Em Linux/macOS, substituir `py -3` por `python3`. A análise de URL é passiva:
não visita o endereço, não consulta DNS nem verifica reputação ou malware.
Pode repetir `--url` até dez vezes.

Para Python, usar o ambiente onde o Bandit foi instalado segundo o
[guia de utilização](USAGE.md). Exemplo, com `.venv` já preparado:

```powershell
.\.venv\Scripts\python.exe -m gensia.agents audit --workspace . --code gensia
```

Opcionalmente, acrescentar `--model NOME_DO_MODELO_LOCAL` à auditoria para pedir
recomendações ao revisor. O modelo precisa de estar instalado no Ollama em
`http://127.0.0.1:11434`. O comando não instala modelos nem muda para cloud.
O revisor recebe achados estruturados, incluindo caminhos relativos e mensagens
do scanner; não recebe o campo de código-fonte nem URLs completas.

Para estudar documentos:

```powershell
py -3 -m gensia.agents study --workspace C:\Estudos --model NOME_DO_MODELO_LOCAL "Como funciona NAT?" redes.md
```

O tutor precisa de um modelo local. Envia para esse modelo a pergunta e os trechos
recuperados dos ficheiros explicitamente indicados, confinados ao workspace. As
citações são verificadas estruturalmente; não provam a correção da resposta.

## Resultados e falhas

Cada execução imprime JSON com `steps`, IDs de evidência e estados `completed`,
`partial`, `failed` ou `skipped`. Código de saída 0 indica etapas concluídas;
11 indica falha ou resultado parcial. Erros de argumentos usam o código 2 do
argparse. Um relatório concluído pode conter vulnerabilidades: `complete` não
é um veredicto de segurança nem deve servir como política de aprovação de código.

Falhas num alvo preservam evidências dos restantes. Se não houver evidências,
o revisor é omitido. Scans incompletos continuam marcados como parciais. O revisor
recebe até 30 achados por scan, ordenados por severidade entre os resultados
retidos pelo scanner; omissões são indicadas por `incomplete_evidence` e
`omitted_issues`. O próprio adaptador Bandit pode truncar resultados anteriormente.

O registo de ações fica por omissão em `~/.gensia/agents.jsonl`, configurável com
`--audit-log CAMINHO`. O log regista ações/estados e hashes, sem respostas do modelo
nem documentos. O JSON impresso pode conter URLs e trechos de documentos: não o
publique sem revisão. Esta equipa escreve o log, mas não altera o código analisado.

Nenhuma resposta do modelo é executada. Não há envio de emails, consulta automática
ao VirusTotal, fallback cloud ou aplicação de correções. Bandit não oferece uma
sandbox de sistema operativo; mantenha código hostil num ambiente isolado.

## Validação e continuidade

Em 14/10/2026: 129 testes passaram, incluindo 12 novos testes da equipa. CLI
real exercitada com URL pública sem acesso à rede. Recuperação documental usa
ficheiros temporários reais; geração Ollama e resultados Bandit usam simulações.
Ollama/Bandit reais e execução em Windows ainda não foram validados nesta etapa.

Próximo passo: teste de integração com os dois motores reais e um projeto de
exemplo; depois expor os relatórios no painel local. Não existe serviço em
segundo plano instalado no computador do utilizador.

Referência consultada em 14/10/2026: API oficial Ollama,
https://docs.ollama.com/api/chat — protocolo já usado pelo adaptador existente.
Não foi adotado um novo modelo, framework ou benchmark nesta etapa.
