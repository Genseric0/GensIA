# Voz local: alterações e validação — 21/10/2026

Este módulo fornece transcrição explícita de ficheiros, síntese para WAV e
gravação limitada do microfone. Não executa comandos ditados nem mantém escuta
contínua. A interface web não deve apresentar motores como funcionais sem os
testar na máquina alvo.

## Alterações

- Whisper exige `--checkpoint` apontando para pesos `.pt` locais confiáveis.
  A validação ocorre antes da importação do motor; não se passa o nome de um
  modelo ao mecanismo de descarga do Whisper. `--model` conserva o rótulo
  configurado nos resultados: os pesos realmente usados são definidos pelo
  checkpoint. O rótulo não autentica nem identifica o conteúdo dos pesos.
- Checkpoint: ficheiro regular de 1 byte a 4 GiB, sem symlinks, hardlinks ou
  reparse point Windows detetável. Áudio limitado pelo `--max-mib` e extensões
  permitidas; idioma validado. Resposta do motor validada e erros privados
  substituídos por mensagens fixas.
- Piper recebe texto por stdin, nunca como argumento do subprocesso. `--stdin`
  permite também evitar o texto na linha de comando da própria GensIA.
  Máximo 5000 caracteres, 20000 bytes UTF-8 de stdin, com validação estrita.
  stdout/stderr do motor vão para DEVNULL; o subprocesso tem timeout, modo
  Python isolado e não usa shell.
- WAV temporário reservado por `mkstemp`, ficheiro regular sem hardlinks,
  tamanho entre 12 bytes e 64 MiB. Apenas 12 bytes são lidos para assinatura
  RIFF/WAVE; não se afirma validação completa da estrutura/qualidade do áudio.
- Publicação sem overwrite usa criação exclusiva por hardlink; se o destino
  surgir durante a síntese, é preservado. Substituição de áudio exige booleano
  exato `True` / flag explícita `--approve-overwrite` tanto no Piper como no
  gravador. Sistemas de ficheiros sem hardlinks podem recusar publicação;
  não há fallback que permita substituir silenciosamente.

## Execução local

Os comandos seguintes são instruções para o operador. Não foram executados com
motores reais nesta revisão. Usar Python suportado, ambiente virtual e pacotes
opcionais compatíveis, FFmpeg para Whisper, drivers/dispositivo para microfone.
Verificar previamente origem, hash e licença dos pesos, voz e respetiva
configuração `.onnx.json`; não carregar checkpoints desconhecidos. Ver
`docs/REAL_ENGINE_VALIDATION.md` para a validação de motores na máquina alvo.

```sh
python -m gensia voice transcribe amostra.wav --checkpoint /caminho/seguro/base.pt --model base --language pt --device cpu
python -m gensia voice synthesize --stdin --voice /caminho/seguro/voz.onnx --output resposta.wav < texto.txt
python -m gensia voice devices
python -m gensia voice record --output amostra.wav --duration 5 --sample-rate 16000
```

Os destinos devem estar numa pasta existente controlada pelo operador. Omitir
`--approve-overwrite` preserva destinos existentes. Não usar texto confidencial
como argumento posicional: pode ficar visível no histórico/processos. A saída
da transcrição e os WAV contêm dados pessoais; protegê-los e apagá-los segundo
a política do utilizador.

## Validação efetiva

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_voice*.py' -q
```

**28 testes aprovados, zero falhas.** O incremento cobre overwrite com valores
verdadeiros indevidos; destino que surge durante síntese; stdin limitado e
UTF-8; ausência de texto em argv e de stderr refletido; checkpoint obrigatório,
links, tamanho e tipo; outputs de transcrição inválidos e erro controlado no
terminal. Motores, dispositivos e processos de síntese usam doubles de teste.

Não foram instalados/validados Whisper, Piper, FFmpeg, PortAudio ou modelos;
não se mediram latência, precisão, qualidade sonora, consumo de memória/GPU,
compatibilidade Windows/macOS nem português moçambicano real. A invocação é
local, mas não existe sandbox de rede do motor (`network_isolated: false`).
CPU, duração da transcrição e comportamento de dependências nativas não têm
isolamento forte. Operar com modelos/diretórios confiáveis e verificar os
motores reais antes de disponibilizar voz a clientes.
