# Entrega — alvo22/10/2026 — revisão21/10/2026

**RELEASE BLOCKED** para distribuição comercial. Incremento0.61.0 preparado
para revisão e ensaio local controlado; não existe garantia de zero falhas.
O incremento0.62 acrescenta `memory check`, com377 testes locais aprovados.
O incremento0.63 corrige publicação parcial de backup/restauro e acrescenta
ensaios de interrupção:394 testes locais PASS. Hot journals e órfãos continuam
a exigir intervenção explícita; ver MEMORY_RECOVERY.md. Sem ensaio físico de
disco cheio/corte de energia. O CI corrente deve ser consultado no PR.
O incremento0.64 acrescenta recuperação de hot journal somente numa cópia,
com consentimento específico, hashes e validação de notas;413 testes locais
PASS. Não impõe lock à origem e não suporta WAL/multi-base. O ensaio não
substitui validação operacional no hardware alvo ou recuperação física.
Os [checks do PR1](https://github.com/Genseric0/GensIA/pull/1/checks) indicam o
estado do commit atual. A tabela e run específico abaixo preservam a baseline0.61.

| Critério | Estado e evidência |
| --- | --- |
| Baseline reproduzível | PASS: commit206f4d1 em worktree separado,277 testes completos |
| Código inicia / pacote instalável | PASS Linux/Python3.12: CLI/API/HTTP e wheel isolado |
| Regressão essencial | PASS Linux:366 Python e44 Node; ver TEST_REPORT.md |
| Correções P1 conhecidas da auditoria | Implementadas e com regressões; nenhum P0 estabelecido |
| Dados sintéticos e recuperação | PASS: concorrência, rollback, integridade e backup/restauro |
| Vulnerabilidades conhecidas da resolução instalada | Zero no pip-audit; Bandit sem médios/elevados |
| Interface real e acessibilidade visual | Chromium remoto PASS; quatro PNG inspecionados; auditoria completa de acessibilidade pendente |
| Modelo/voz reais | PENDENTE: pesos, dispositivos, desempenho e privacidade do daemon |
| Windows e Python3.13 | PASS no CI Linux/Windows3.12/3.13; hardware e aplicações interativas pendentes |
| CI obrigatório verde | PASS: [run39521033113](https://github.com/Genseric0/GensIA/actions/runs/39521033113), seis jobs aprovados no commit04a8660 |
| GitHub atualizado / PR | PASS: [PR1](https://github.com/Genseric0/GensIA/pull/1), draft, sem merge |
| Venda / vários clientes | BLOQUEADO: produto ainda local por utilizador, sem identidade/RBAC/isolamento entre clientes |
| Licenças e distribuição | BLOQUEADO: titular deve definir licença do projeto e direitos dos pesos/vozes |

## Prioridades para fechar a entrega

Evidência remota consultada em 21/10/2026: commit
`04a866059fd65c1d7079c14b20f41ac620c76e02`, workflow completo `success`.
Linux:366 Python e44 Node por configuração, sem omissões. Windows:341 Python
aprovados/25 omissões POSIX/Linux e44 Node por configuração. Build e instalação
isolada passaram nas quatro configurações. Segurança e Chromium também passaram.
As omissões não validam proteções POSIX em Windows. Detalhes em TEST_REPORT.md.

1. Manter os checks do PR verdes; a publicação e a execução inicial estão concluídas.
2. Complementar o Chromium aprovado com teclado, contraste, leitor de ecrã e
   restantes percursos alvo, sem confundir modelo sintético com inferência.
3. Num computador de teste autorizado, iniciar Ollama com cloud desativada,
   pesos locais verificados e medir conversa, cancelamento, RAM e latência.
   Ensaiar áudio com checkpoint/voz locais, sem dados pessoais iniciais.
4. Validar instalador/atualizações, ACL Windows, recuperação após falha/disco
   cheio, retenção/rotação de auditoria e matriz de sistemas suportados.
5. Definir licença, modelo comercial, suporte e segregação por instalação.
   Um serviço partilhado exigirá autenticação/autorização e arquitetura própria.

Main não é alterada. Não há deployment em produção, migração de dados reais,
envio de emails ou autorização geral para ações externas. As confirmações CLI
continuam específicas. Não existe processo contínuo de IA configurado por esta
documentação; GitHub Actions executa somente os eventos configurados.
