# Entrega — alvo22/10/2026 — revisão21/10/2026

**RELEASE BLOCKED** para distribuição comercial. Incremento0.61.0 preparado
para revisão e ensaio local controlado; não existe garantia de zero falhas.

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
| Windows e Python3.13 | PENDENTE de execução do CI e ensaio em hardware alvo |
| CI obrigatório verde | PENDENTE: configuração não equivale a execução aprovada |
| GitHub atualizado / PR | PASS: [PR1](https://github.com/Genseric0/GensIA/pull/1), draft, sem merge |
| Venda / vários clientes | BLOQUEADO: produto ainda local por utilizador, sem identidade/RBAC/isolamento entre clientes |
| Licenças e distribuição | BLOQUEADO: titular deve definir licença do projeto e direitos dos pesos/vozes |

## Prioridades para fechar a entrega

1. Publicar branch, abrir PR e consultar resultados reais dos jobs; corrigir falhas.
2. Executar o runner Chromium e inspecionar PNG reais, sem confundir modelo
   sintético com inferência. Validar teclado, contraste e todos os percursos alvo.
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
