# Interface executada em Chromium — 21/10/2026

Capturas reais, descarregadas do artifact `chromium-conversation-evidence` do
[job118961545502](https://github.com/Genseric0/GensIA/actions/runs/39520092421/job/118961545502).
Commit executado: `18a87ae323922a0720a5c3c898d38825be91c48e`.

O job terminou com sucesso e validation.json contém `passed:true`, oito grupos
de verificações e quatro PNG. O servidor de teste usa o mesmo `create_app` e os
mesmos assets da aplicação; só o provider é sintético, claramente identificado
nas respostas. `real_inference_tested:false`. Não são imagens geradas por IA.

| PNG | Viewport |
| --- | --- |
| chat-desktop.png |1440×1000 |
| chat-768.png |768×1000 |
| chat-390.png |390×1000 |
| chat-320.png |320×1000 |

As quatro imagens foram inspecionadas visualmente: conversa, formulário e
navegação legíveis, sem corte horizontal observado. O runner também verificou
overflow, continuidade, HTML tratado como texto, erros, cancelamento, limpeza,
ausência de storage/cookies e token inválido. Esta inspeção não substitui uma
auditoria de contraste/leitor de ecrã nem valida todos os módulos do terminal.

Artifact12310457652, ZIP367906bytes. SHA256 confirmado antes da extração:
`d98f98fec751a3d52dcc68247ff594b8acf213d9dd027100bca0c74766c16257`.
O workflow global inicial teve falhas separadas na auditoria de pacote editable
e na suíte Windows; aprovação deste job não significa aprovação da release.
O manifesto local anterior `../chat-browser-2026-10-21/validation.json`
continua preservado como evidência do bloqueio de download neste ambiente.
