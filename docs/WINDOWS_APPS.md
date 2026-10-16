# Abrir aplicações Windows — v0.24.3

Na raiz do projeto, em Windows, o comando seguinte pede a abertura do Notepad:

```powershell
py -3 -m gensia tool open-app notepad --approve
```

Outras opções permitidas: `calculator` e `files` (Explorer). A operação exige
`--approve` e mantém auditoria local. Não permite executáveis ou argumentos livres.

## Resolução

| Opção | Diretório consultado | Ficheiro |
| --- | --- | --- |
| calculator | GetSystemDirectoryW | calc.exe |
| notepad | GetSystemDirectoryW | notepad.exe |
| files | GetSystemWindowsDirectoryW | explorer.exe |

O caminho é obtido com ctypes/Kernel32; não é construído a partir de PATH,
SystemRoot ou WINDIR. `subprocess.Popen` recebe o caminho absoluto também em
`executable`, com `shell=False`, sem argumentos adicionais. O diretório de trabalho
do filho é o diretório de sistema consultado. Se a consulta ou o arranque falharem,
devolve ToolError e regista erro; não tenta outro executável pelo nome.

Caminhos relativos, UNC, caminhos com traversal/ADS ou formatos não canónicos
são recusados. Instalações Windows na raiz da unidade não são suportadas nesta
política estrita. Não existe verificação de assinatura Authenticode nem sandbox:
a confiança nos executáveis e permissões dos diretórios é a do Windows instalado.
DLLs e dependências dos processos não são isoladas por esta alteração.

## Evidência

Sete testes novos em `tests/test_windows_launcher.py` usam WinAPI e criação de
processos simuladas. Testam também ambiente com PATH/SystemRoot/WINDIR adversos,
negação sem confirmação e falhas sem fallback. A suite completa passou com 195
testes em Linux. Nenhuma aplicação foi aberta neste ambiente nem no computador
do utilizador. Ainda falta Windows real, incluindo Python 32/64-bit, WOW64 e
wrappers modernos de Calculator/Notepad. Um Popen bem-sucedido não prova que uma
janela ficou utilizável ou que o processo não falhou depois.

Reprodução das verificações simuladas (qualquer SO com Python 3.10+):
`python -m unittest discover -s tests -p test_windows_launcher.py -v`.

Fontes primárias consultadas em 16/10/2026:
[GetSystemDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemdirectoryw),
[GetSystemWindowsDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemwindowsdirectoryw),
[CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw).
Sem novas dependências de produção.
