# Changelog

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
