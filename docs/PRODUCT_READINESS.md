# Preparação para uso pessoal e clientes

Revisão de 16/10/2026, atualizada na v0.32.0. Estado: protótipo local; **lançamento comercial
geral ainda não aprovado**. Os testes validam casos concretos, não ausência de falhas.
Inspeção e reprodução a partir do próprio código existente, sem binários de terceiros.

## Correções entregues nesta revisão

| Problema reproduzido | Comportamento corrigido | Evidência |
| --- | --- | --- |
| AuditLogger seguia symlink cujo destino não existia | Recusa o link e não cria o destino | Teste com sistema de ficheiros temporário |
| Erros de permissões escapavam como OSError | ToolError com mensagem sem caminho privado | Falha de abertura injetada |
| Troca do último componente durante abertura do log | O_NOFOLLOW onde disponível; valida tipo e número de links pelo descritor | Troca check/open reproduzida em POSIX |
| Erro HTTP Ollama podia provocar TypeError ou leitura sem limite | Corpo de erro HTTP não é lido; resposta fechada; mensagem controlada | Corpos de erro texto/dict/list e leitura monitorizada |
| Erros Ollama podiam expor conteúdo privado e sequências de terminal | Mensagem genérica para erros HTTP/JSON | Conteúdo sintético SECRET não aparece na exceção pública |
| Porta inválida ou caminho extra falhava tarde | Validação da URL na configuração | Casos de porta, caminho e controlos |

A auditoria também recusa hard links adicionais e ficheiros não regulares. Em POSIX,
logs novos usam 0600 e a pasta final nova usa 0700; permissões preexistentes não são
alteradas. Não existe garantia equivalente de ACL no Windows.

## Modelo inicial de entrega

Primeiro produto alvo: aplicação **local por utilizador do sistema operativo**,
com dados e credenciais exclusivos dessa instalação. Uma instalação de teste por
cliente é a hipótese inicial de arquitetura, ainda não um instalador disponível.
O token único atual não representa identidade de cliente nem controlo de funções.
Não alojar esta API como serviço partilhado entre clientes ou expô-la na Internet.

O [diagnóstico de proteções](PROTECTIONS.md) informa capacidades e quotas previstas
no ambiente, sem aplicar limites ou aprovar a instalação. Nem preflight_passed do
doctor nem a saída 0 de protections substituem os critérios de piloto abaixo.

| Dados | Estado atual | Necessário antes do piloto com dados reais |
| --- | --- | --- |
| Notas | Backup JSON v1 e restauro para DB nova testados em Linux, até 1000 notas/8 MiB | Falhas durante cópia/crash, Windows real, política de retenção e permissões verificadas |
| Auditoria | JSONL: data, ação, resultado, fingerprint truncado do alvo | Rotação, política de retenção e indicação de falha após ação |
| Documentos | Abertura POSIX ancorada por descritores; worker PDF com quotas Linux e recuperação testada | Equivalente Windows, quotas agregadas, snapshot sob escrita hostil e sandbox |
| Credencial API | Token por processo via ambiente; painel de diagnóstico usa Bearer só em memória JS | Fluxo de browser real, revogação/rotação assistida e secret store do SO |
| Modelos | Ollama local; sem fallback cloud automático | Inferência real e limites de RAM/latência verificados por configuração suportada |

O fingerprint SHA-256 truncado não é anonimização: alvos previsíveis podem ser
adivinhados. A auditoria não é inviolável, não tem fsync/assinatura e não prova
execução bem-sucedida se a aplicação externa arrancar e depois falhar.

## Bloqueios por prioridade

1. Segurança dos acessos locais: diretórios-pai da auditoria devem ser confiáveis;
   O_NOFOLLOW protege o último componente apenas onde existe. Memória/documentos
   ainda não têm isolamento robusto contra outro processo hostil com as mesmas
   permissões. Documentos usam descritores POSIX na v0.30.0; o caminho Windows
   continua sem essa proteção contra trocas concorrentes. Abertura de aplicações
   Windows passou a usar caminhos absolutos consultados pela
   WinAPI na v0.24.3; requer teste real de compatibilidade, wrappers e permissões
   dos diretórios de sistema. Não executar a GensIA como administrador.
2. Operação: backup/restauro, migrações SQLite, recuperação após disco cheio,
   rotação de logs e quotas agregadas/Windows para PDF. Tetos Linux por worker
   existem na v0.29.0; não substituem isolamento nem limites de toda a instalação.
3. Integrações: inferência Ollama, Whisper/Piper/microfone e GUI em hardware real;
   painel de diagnóstico tem HTTP/Node/VM testados, mas browser/layout e capturas
   reais continuam pendentes. Mock não equivale a validação do motor/browser.
4. Distribuição: instalador reproduzível, atualização/rollback, matriz de sistemas
   suportados, testes Windows e inventário de dependências/licenças dos modelos.
5. Comercial: pacote de suporte, escopo contratado e política de dados. Não foi
   encontrada licença do projeto nesta revisão; decidir distribuição/licenciamento
   antes da entrega comercial. Não copiar código de referências sem rever licença.
6. Serviço para vários clientes (futuro): identidades, isolamento por cliente,
   quotas, controlo de acesso, autenticação forte e testes de isolamento. Não está
   implementado e não deve ser inferido da presença de FastAPI.

## Critérios para piloto limitado

- Zero regressões conhecidas no escopo de piloto; suite completa e HTTP real verdes.
- Fluxos contratados exercitados num Windows suportado, por conta sem privilégios.
- Modelo escolhido a responder realmente e medidas de RAM/tempo documentadas.
- Backup restaurado numa instalação limpa, sem mistura de dados de instalações.
- Falhas de permissão, serviço desligado e disco cheio com resultado compreensível.
- Dependências e licenças inventariadas; dados sintéticos antes de dados do cliente.

Só após esse piloto se pode avaliar venda e suporte de uma configuração concreta.
A documentação não ativa monitorização nem processos permanentes.

## Referências técnicas da correção

Consultadas em 16/10/2026, sem novas dependências de produção:
[Python 3.12 os/open](https://docs.python.org/3.12/library/os.html#os.open),
[urllib HTTPError](https://docs.python.org/3.12/library/urllib.error.html#urllib.error.HTTPError).

Reproduzir regressões: `python -m unittest discover -s tests -p test_security_regressions.py -v`.
Para a suite com socket real, consultar docs/API_REPORT.md.
