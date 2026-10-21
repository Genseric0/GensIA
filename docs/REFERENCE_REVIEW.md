# Referências revistas — 21/10/2026

Esta revisão preserva Python/SQLite/FastAPI e não importa código de outros
assistentes. Consulta pública não implica validação de execução, segurança ou
licença de todos os componentes desses projetos.

| Fonte primária | Observação e decisão para a GensIA |
| --- | --- |
| [Ghost AI Assistant](https://github.com/ghostempireis/Ghost-AI-Assistant) | README descreve ativação e inatividade. Esses padrões ajudam a rever estados explícitos da sessão. Não se adotou o fallback cloud ou o controlo de aplicações por texto gerado; não se executou o projeto nem se verificaram as suas alegações funcionais. |
| [Pipecat: terminação](https://docs.pipecat.ai/pipecat/learn/pipeline-termination) | Distingue drenagem de trabalho e cancelamento com limpeza. Na GensIA, cancelar a espera do browser não é apresentado como cancelamento da inferência: o worker mantém o lock até terminar. Uma futura pipeline de voz precisa de supervisionar e encerrar todos os seus recursos. Pipecat não foi instalado. |
| [Open computer use](https://github.com/coasty-ai/open-computer-use) | Abertura da página e README de production devolveu404 nesta consulta. A pesquisa encontrou referências indexadas, mas não se usaram percentagens de benchmark ou rótulos production-ready como prova, nem se copiou implementação inacessível. |
| [Goose](https://github.com/aaif-goose/goose) | Avaliado como ferramenta opcional; não disponível/configurado nesta execução. O trabalho foi feito com Codex e agentes efetivamente executados. Não há runner de Goose configurado. |
| [Ollama: show](https://docs.ollama.com/api/show) e [FAQ](https://docs.ollama.com/faq) | Gate de metadados antes de prompts; cloud deve ser desativada no daemon. A política depende de daemon confiável; não atesta tráfego ou pesos. |
| [OWASP ASVS5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0) | Áreas aplicáveis documentadas em SECURITY_AUDIT.md; sem certificação ou cobertura integral alegada. |
| [pip-audit](https://github.com/pypa/pip-audit) e [concorrência GitHub](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) | Comandos e CI confrontados com documentação primária e execução real; falhas encontradas foram corrigidas, sem ignorar advisories. |

As versões/licenças declaradas e limites de compatibilidade das dependências
adotadas constam de DEPENDENCIES.md. Não se instalaram novas stacks de agentes,
modelos, motores de voz ou serviços cloud. Não houve engenharia reversa de
binários proprietários; o diagnóstico e as correções resultam de revisão do
código autorizado, reprodução de defeitos e testes defensivos.
