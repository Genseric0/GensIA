# Changelog

## 0.66.0 — ensaio explícito do modelo — 21/10/2026

- Comando model_probe com aprovação, frase sintética fixa e1–3 amostras.
- Tempos de chamadas completas, sem conteúdo/nome do modelo/endpoint na saída.
- Falha parcial/interrupção não aprovam teste; sem fallback ou novas rotas.
- Dez regressões e verificação de empacotamento do novo comando.


## 0.65.0 — configuração guiada na interface — 21/10/2026

- Guia expansível com etapas separadas de API, metadados e primeira resposta.
- Instruções manuais e orientação específica por erro, com texto fixo seguro.
- Progresso reposto em logout/expiração, nova conversa e nova verificação;
  respostas tardias não restauram uma sessão terminada.
- Seis regressões Node e runner Chromium ampliado; sem novas rotas/dependências.

## 0.64.0 — recuperação assistida numa cópia — 21/10/2026

- CLI recover-copy, com aprovação e declaração específica de origem parada.
- Captura de bytes/hash, rollback só em cópia privada, notas validadas e esquema
  canónico publicado num destino novo. Nunca abre a origem pelo SQLite.
- Guardas de WAL, super-journals, expansão por header, origem alterada, links,
  tamanhos, schema adicional e auxiliares antigos no destino.
- Restauro JSON também recusa auxiliares antigos;19 regressões novas e pacote
  instalado validado em9 etapas. Manual e resultados em MEMORY_RECOVERY/TEST_REPORT.
- Sem lock imposto à origem, reparação física, WAL ou novas dependências.
- CI expôs ordem variável de diretórios e diferença ctime stat/fstat no Windows;
  asserção corrigida e comparações de metadados feitas entre APIs compatíveis.

## 0.63.0 — publicação de backup/restauro — 21/10/2026

- Corrigido destino parcial visível após falha de gravação/fsync: preparação
  privada, sincronização e publicação exclusiva sem sobrescrever concorrentes.
- Metadados distinguem destino publicado, sincronização e limpeza; avisos após
  publicação indicam que não se deve repetir automaticamente.
- Ensaios de término real de processos, SQLITE_FULL, rollback DELETE/WAL,
  competição de destino e falhas ENOSPC injetadas; nenhum dado real utilizado.
- Documentados hot journals, órfãos e a janela de hard link POSIX; sem reparação
  silenciosa nem novas dependências. Estado comercial permanece RELEASE BLOCKED.

## 0.61.0 — candidata de hardening — 20–21/10/2026

Base:remote0.34.0,SHA206f4d1798d516deccb3268938777b1348cfb85b. Pacotes locais
posteriores não estavam recuperáveis no ambiente atual;não se afirma que todos os
incrementos0.35–0.60 foram restaurados. A base real foi auditada e testada novamente.

- Conversa web sobre FastAPI/Ollama,contexto limitado e sessão apenas no navegador.
- Aprovação exata e intenção de auditoria durável antes de abrir aplicações.
- Metadados locais antes de prompts;JSON,Unicode e controlos de terminal validados.
- SQLite com criação0600,recusa de links e leitura/backup limitados e validados.
- Backup sem perda silenciosa noNUL;regressão de recuperação em base nova.
- Voz com checkpoint explícito,stdin para Piper e aprovação exata de sobrescrita.
- Reserva da porta antes de revelar token temporário.
- Wheel,extras opcionais e workflows de testes,dependências e segurança.
- Auditoria inicial,segurança,dados,QA e checklist com evidências verificáveis.

O estado final e o commit validado são registados em TEST_REPORT/RELEASE_CHECKLIST.
# Correções após execução real de CI — 21/10/2026

- Windows: recusados destinos symlink antes de criação de export/backup/restauro.
- Fixtures SQLite fecham conexões explicitamente, mantendo transações; novas
  regressões confirmam fecho/rollback e guardas antes de efeitos.
- Relatórios estáticos normalizam caminhos relativos com `/` em todas as plataformas.
- Auditoria strict usa inventário de todas as dependências não editable, com
  verificação de que apenas a própria GensIA é editable.
- Chromium E2E aprovado remotamente; quatro capturas reais verificadas e guardadas.
- Concorrência do CI evita duplicar push/PR da mesma branch e distingue forks.

# v0.62.0 — 21/10/2026

- Comando `memory check` para integridade SQLite e notas, numa transação de leitura.
- Limites por ligação/VM/tempo; erros e relatórios sem conteúdo das notas.
- Onze regressões de corrupção, WAL, limites, CLI e recuperação para base nova.
- Manual operacional em MEMORY_RECOVERY.md. Sem novas dependências ou reparação automática.

