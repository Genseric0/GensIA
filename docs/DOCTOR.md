# Diagnóstico local — atualizado na v0.31.0

Na v0.66, o ensaio separado [model_probe](MODEL_PROBE.md) permite enviar uma
frase sintética com --approve e medir chamadas completas sem imprimir respostas.
O doctor abaixo continua apenas a consultar metadados/listagem, sem inferência.

Antes de iniciar os agentes, na pasta do projeto:

```powershell
py -3 -m gensia.doctor --model qwen2.5:0.5b
```

Se as dependências estiverem num ambiente virtual, usar o mesmo interpretador
dos agentes: `.\.venv\Scripts\python.exe -m gensia.doctor --model qwen2.5:0.5b`.
Em Linux/macOS pode usar `python3 -m gensia.doctor`.

O nome é apenas um exemplo: especificar a etiqueta exata de um modelo local que
tenha sido escolhido e instalado pelo utilizador. O comando não escolhe modelos,
não instala Bandit, não descarrega pesos e não inicia serviços.

## O que verifica

- Bandit: metadados da distribuição e presença do módulo no Python atual, sem
  importar o motor nem executar um scan. Versão presente não prova compatibilidade.
- Ollama: um único pedido GET `/api/tags` ao endpoint local, sem corpo ou prompt.
- Modelo: correspondência exata com a etiqueta devolvida pelo servidor. Não usa
  aliases implicitamente: `modelo` e `modelo:latest` não são tratados como iguais.
- Documentos: capacidades de abertura por descritores e backend de quotas Linux,
  sem aplicar limites nem abrir ficheiros pessoais. Ver [interpretação](PROTECTIONS.md).

Usa o transporte existente, sem proxies do ambiente ou redirecionamentos HTTP.
Não lê documentos, não consulta memória nem guarda relatório automaticamente.
Só imprime JSON. Não mostra a lista completa de modelos, nem corpos de erro HTTP.
O nome explicitamente pedido pode aparecer no relatório.

## Estados e códigos de saída

| Estado | Significado |
| --- | --- |
| Bandit `available` | Metadados e módulo encontrados, execução não testada |
| Bandit `missing` / `unavailable` | Distribuição ausente ou instalação não resolvida |
| Ollama `reachable` | API devolveu uma listagem interpretável |
| Ollama `unavailable_or_invalid` | Falha de ligação, HTTP ou resposta inválida |
| Modelo `listed` | Etiqueta exata apareceu na listagem |
| Modelo `missing` | API respondeu, mas não listou a etiqueta |
| Modelo `not_selected` | Não foi fornecido `--model` |
| Modelo `not_checked` | Não foi possível consultar a API |

Saída **0**: Bandit encontrado e modelo listado (`preflight_passed=true`).
Saída **12**: algum pré-requisito não confirmado. Saída **2**: argumentos inválidos.
Sem `--model`, o comando faz as outras verificações, mas não aprova a equipa completa.

`preflight_passed` não certifica inferência, disponibilidade de RAM/GPU, pesos
utilizáveis, qualidade ou execução sem cloud. Mesmo um servidor em loopback pode
encaminhar pedidos: usar pesos locais e desativar cloud na configuração do Ollama.
Os campos `inference_validated` e `execution_validated` permanecem falsos neste
diagnóstico. Para a validação real, usar `scripts/validate_agents_real.py`.
O campo checks.document_protections é informativo e não altera preflight_passed.
Para consultar apenas proteções, **sem o pedido local ao Ollama**, executar
`python -m gensia.protections`; esse comando não exige dependências opcionais.

## Configuração

```powershell
py -3 -m gensia.doctor --model qwen2.5:0.5b --endpoint http://127.0.0.1:11435 --timeout 3
```

Apenas HTTP em `127.0.0.1`, `localhost` ou `::1`, sem caminho extra, credenciais,
query ou fragmento. Timeout entre 0,1 e 10 segundos, aplicado ao transporte; não
é uma garantia de prazo total perante um servidor malicioso. Nenhuma comunicação
com serviços externos é iniciada pelo comando. Não há fallback cloud.

## Evidência — 14/10/2026

141 testes passaram, incluindo dez testes novos do diagnóstico. Um servidor HTTP
de teste real confirmou apenas GET `/api/tags`, sem corpo; a sua listagem era
sintética, não inferência Ollama. Foram verificados estados, privacidade de erros,
ausência de seleção automática, etiquetas exatas, entradas inválidas e exit codes.

Execução real da CLI neste ambiente: Bandit 1.9.4 disponível; Ollama inacessível;
modelo `not_checked`; saída 12. Não se repetiu o download anteriormente bloqueado.
Scan Bandit real sobre os 16 módulos: três LOW B404, zero MEDIUM/HIGH. Nenhum
motor/modelo foi instalado no computador do utilizador. Geração real continua
pendente até existir um modelo acessível no ambiente de execução.

Referência primária consultada em 14/10/2026:
[GET /api/tags — documentação oficial Ollama](https://docs.ollama.com/api/tags).
Não foram adotadas novas dependências, modelos ou alegações de desempenho.
