# Uso da Biblioteca Padrão do CGD no DCC

O DCC utiliza exclusivamente módulos reais da biblioteca padrão do **CGD** instalada em `~/.delegua/cgd`, inspecionados diretamente no código-fonte da versão instalada (**CGD ≥ 0.9.0**).

---

## 1. Versão Mínima Suportada e Verificação

- **Versão mínima do CGD**: `0.9.0` (testado com `CGD - Compilador Geral Delégua v0.9.0`).
- **Detecção no build**: `bootstrap/build.sh` verifica a existência do executável `cgd` e imprime `cgd --versao` antes de compilar `src/main.delegua`.
- **Sem dependências de detalhes internos não documentados**: todas as chamadas usam apenas classes/métodos públicos exportados pelos módulos `cgd:*` listados abaixo.

---

## 2. Inventário Completo de Módulos `cgd:*` Utilizados

| Módulo `cgd:*` | APIs Utilizadas | Onde é Usado | Finalidade |
| :--- | :--- | :--- | :--- |
| `cgd:ambiente` | `Ambiente.existe(nome)`, `Ambiente.obter(nome)` | `src/diagnostics/diag.delegua` | Verificação de `NO_COLOR` para cores ANSI |
| `cgd:arquivos` | `Arquivo(caminho).ler()`, `Arquivo(caminho).escrever(txt)`, `Arquivo.existe(caminho)`, `Diretorio.existe(caminho)` | `src/driver/cli.delegua`, `src/preprocessor/preproc.delegua` | Leitura de `.c`/`.h`, escrita de `.s`/`.i` e busca de headers/archives |
| `cgd:bytes` | `Bytes.deTexto(txt).paraVetor()`, `Bytes.deVetor(vet).paraTexto()`, `Bytes.deVetor(vet).paraBase64()`, `Bytes.deBase64(b64).paraVetor()` | `src/driver/cli.delegua`, `src/preprocessor/preproc.delegua`, `src/lexer/lexer.delegua`, `src/ir/ir_tipos.delegua`, `src/object/elf/elf_obj.delegua`, `src/linker/elf_leitor.delegua`, `src/linker/linker.delegua` | Conversão texto ↔ UTF-8, codificação Base64 para I/O binário ELF64 |
| `cgd:caminhos` | `Caminhos.diretorio(p)`, `Caminhos.juntar(a, b)`, `Caminhos.ehAbsoluto(p)`, `Caminhos.extensao(p)`, `Caminhos.trocarExtensao(p, ext)` | `src/driver/cli.delegua`, `src/preprocessor/preproc.delegua` | Manipulação padronizada de caminhos (substituindo código manual anterior) |
| `cgd:io` | `IO.erroLinha(txt)` | `src/driver/cli.delegua` | Emissão de erros, avisos e `-ftime-report` diretamente em `stderr` |
| `cgd:json` | `Json.formatar(obj)` | `src/diagnostics/diag.delegua` | Serialização de diagnósticos para `-fdiagnostics-format=json` |
| `cgd:nativo` | `Primitivas.codigoUnicode(c)`, `Primitivas.caractereUnicode(cp)`, `Primitivas.numeroFinito(x)`, `Primitivas.numeroTexto(x)` | `src/lexer/literais.delegua`, `src/lexer/lexer.delegua`, `src/types/tipos.delegua`, `src/diagnostics/diag.delegua` | Decodificação Unicode, classificação IEEE-754 (`Inf`/`-0.0`) e saída direta |
| `cgd:processo` | `Processo.argumentos()`, `Processo.sair(cod)`, `Processo.executar(prog, args, dir, amb, timeout, limite, entrada)` | `src/main.delegua`, `src/driver/cli.delegua`, `src/preprocessor/preproc.delegua` | Argumentos CLI, código de saída, descoberta via `find` e I/O binário via `base64` |
| `cgd:tempo` | `Cronometro.iniciar()`, `.milissegundos()` | `src/driver/cli.delegua` | Medição por fase de compilação em `-ftime-report` |
| `cgd:textos` | `Textos.comecaCom(s, p)`, `Textos.terminaCom(s, p)`, `Textos.repetir(s, n)` | `src/driver/cli.delegua`, `src/diagnostics/diag.delegua`, `src/preprocessor/preproc.delegua`, `src/linker/linker.delegua` | Prefixos/sufixos e repetição de marcadores `~` em diagnósticos |

---

## 3. FFI Direta com `libc`

Duas funções POSIX simples sem wrapper equivalente em `cgd:*` são declaradas via `@definicao(biblioteca = "c", abi = "c")`:

- `chmod(caminho: texto, modo: inteiro): inteiro` em `src/driver/cli.delegua` (substituindo invocação externa de `chmod` via shell);
- `isatty(fd: inteiro): inteiro` em `src/diagnostics/diag.delegua` (detecção automática de cores ANSI em `stderr`).

---

## 4. Dependências Externas em Runtime

Além do runtime nativo do CGD (`libc`, `libm`, `libpthread` conforme `ldd build/dcc`), o DCC utiliza em tempo de execução apenas:

- `/usr/include` e diretório *freestanding* do sistema (descoberto via `find` de `findutils`);
- `base64` (`coreutils`) para leitura/escrita de arquivos binários `.o`/`.a`/ELF64 (sem interpolação de caminhos em shell; o caminho é passado como argumento posicional `$1`).

Quando o runtime CGD passar a oferecer leitura/escrita binária direta de `Bytes` sem colisão de assinatura C com `<stdio.h>`, a ponte via `base64` poderá ser removida sem alterar o restante da arquitetura.
