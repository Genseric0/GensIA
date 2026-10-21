# Ensaio operacional do modelo — v0.66, 21/10/2026

Com o mesmo Python da GensIA e um modelo local já preparado num Ollama confiável:

```bash
python -m gensia.model_probe --model NOME_LOCAL --approve
python -m gensia.model_probe --model NOME_LOCAL --approve --repeats 3 --timeout 60
```

Sem `--approve`, termina com código2 antes de criar o provider ou contactar o
daemon. A aprovação autoriza uma a três chamadas de geração com uma frase fixa
sintética. Não aceita prompts personalizados, documentos, histórico ou memória.
Não instala dependências/pesos, inicia serviços ou oferece fallback cloud.
Usa o provider existente: loopback HTTP, sem proxies ou redirects; verifica
metadados locais antes de cada geração e recusa metadados cloud/indeterminados.
Não existe endpoint web novo nem execução automática pelo guia da interface.

O JSON inclui tentativas, amostras bem-sucedidas, tempo em milissegundos e códigos
fixos de erro. Omite resposta, nome do modelo, endpoint e mensagens brutas.
Não escreve relatórios automaticamente. O daemon pode ter logs próprios; esta
ferramenta não controla a sua retenção nem prova isolamento.

Código0: resposta válida recebida em todas as chamadas;12: ensaio incompleto;
2: argumentos/aprovação inválidos;130: interrupção tratada durante geração.
Uma falha interrompe a sequência sem retry. Amostras anteriores são preservadas
com `passed=false`. Ctrl+C não garante parar trabalho já recebido pelo daemon.
Timeout1–120s é por pedido HTTP, não prazo global; cada chamada inclui consulta
de metadados e geração, com limites de transporte existentes.

`elapsed_ms` mede toda a chamada, incluindo metadados e carregamento/caches.
Não é latência do primeiro token, tokens/s, medição de RAM/GPU ou benchmark geral.
Não valida significado da resposta, qualidade, segurança, capacidade comercial
ou privacidade de um daemon modificado. Não comparar máquinas com estes números
sem controlar pesos, carga, cache e configuração.

Antes do ensaio, desativar cloud no Ollama (`OLLAMA_NO_CLOUD=1`) e reiniciá-lo,
conforme [FAQ oficial](https://docs.ollama.com/faq), consultada em21/10/2026.
O operador deve verificar essa configuração no daemon. Sem dependências novas.

Testes determinísticos e servidor HTTP sintético local verificam aprovação,
limites, pedidos show→chat, prompt fixo, recusa cloud antes de chat, saída sem
conteúdo, falha parcial, cancelamento, relógio inválido e códigos CLI. Uma
resposta do servidor de teste não comprova inferência com pesos reais.
Não há Ollama/pesos/dispositivos disponíveis neste ambiente. Medição no hardware
alvo continua pendente e RELEASE BLOCKED mantém-se para venda.
