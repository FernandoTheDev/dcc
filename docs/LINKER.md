# Formato ELF64 e Linker Nativo — DCC

O DCC possui emissor próprio de objetos relocáveis ELF64 (`ET_REL`), leitor validado de `.o` e archives estáticos `.a` (formato GNU `ar`), e linker nativo ELF64 (`ET_EXEC`), sem invocar `ld` ou `as`.

---

## 1. Módulos

- [`src/object/elf/elf_comum.delegua`](../src/object/elf/elf_comum.delegua): constantes ELF64 nomeadas (`ET_REL`, `ET_EXEC`, `EM_X86_64`, `SHT_*`, `SHF_*`, `STB_*`, `STT_*`, `SHN_*`, `PT_*`, `PF_*`, `DT_*`, `R_X86_64_*`) e helpers little-endian compartilhados.
- [`src/object/elf/elf_obj.delegua`](../src/object/elf/elf_obj.delegua): serialização de `CodigoObjeto` para ELF64 `ET_REL` (`.o`) com 11 seções:
  1. NULL
  2. `.text` (`PROGBITS`, `AX`)
  3. `.rodata` (`PROGBITS`, `A`)
  4. `.data` (`PROGBITS`, `WA`)
  5. `.bss` (`NOBITS`, `WA`)
  6. `.rela.text` (`RELA`)
  7. `.rela.data` (`RELA` — para inicializadores de ponteiros globais)
  8. `.symtab` (`SYMTAB`, respeitando a regra ELF de `STB_LOCAL` antes de `STB_GLOBAL`/`STB_WEAK`)
  9. `.strtab` (`STRTAB`)
  10. `.shstrtab` (`STRTAB`)
  11. `.note.GNU-stack` (`PROGBITS`, flags `0`, pilha não-executável)
- [`src/linker/elf_leitor.delegua`](../src/linker/elf_leitor.delegua): parser endurecido de `.o` ELF64 e de archives `.a` (`!<arch>\n`, incluindo tabela de nomes estendidos GNU `//` e membros `/`/`/SYM64/`).
- [`src/linker/linker.delegua`](../src/linker/linker.delegua): combinação de múltiplos `.o` e `.a`, resolução de símbolos, aplicação de relocações e emissão do executável dinâmico ELF64 (`ET_EXEC`).

---

## 2. Resolução de Símbolos e Archives `.a`

1. **Símbolos fortes vs fracos (`STB_GLOBAL` vs `STB_WEAK`)**:
   - Dois símbolos fortes definidos com o mesmo nome geram erro explícito (`E5010`).
   - Um símbolo forte prevalece sobre um símbolo `STB_WEAK` (em qualquer ordem de entrada).
   - Chamadas e endereços para símbolos `STB_WEAK` definidos na mesma unidade de tradução emitem relocações simbólicas (`R_X86_64_PLT32`/`R_X86_64_PC32`), permitindo substituição limpa pelo linker.
2. **Símbolos `SHN_COMMON`**: alocados automaticamente na seção `.bss` respeitando alinhamento caso não haja definição inicializada.
3. **Símbolos `SHN_ABS`**: preservam seu endereço absoluto (`st_value`).
4. **Extração iterativa de archives `.a` (`-L`, `-l<lib>` e `lib*.a` direto)**:
   - O linker analisa símbolos indefinidos após os `.o` principais e extrai membros de `.a` em ponto fixo iterativo (resolvendo dependências transitivas entre membros do archive).
   - Apenas os membros efetivamente referenciados são incorporados.

---

## 3. Relocações Suportadas

| Tipo ELF64 | Uso no DCC |
| :--- | :--- |
| `R_X86_64_64` (1) | Ponteiros absolutos em `.data` (`.rela.data`, ex.: strings, `&global`, ponteiros de função) |
| `R_X86_64_PC32` (2) | Acessos RIP-relative a `.rodata`, `.data`, `.bss` e funções locais/globais |
| `R_X86_64_PLT32` (4) | Chamadas a funções locais, globais ou externas via stub PLT |
| `R_X86_64_GOTPCREL` (9), `R_X86_64_GOTPCRELX` (41), `R_X86_64_REX_GOTPCRELX` (42) | Endereços de globais/funções externas via GOT (ex.: `stdout`, `stderr`, objetos GCC/Clang PIC) |
| `R_X86_64_32` (10) / `R_X86_64_32S` (11) | Endereços 32-bit absolutos com verificação de faixa/overflow |

Relocações são processadas em `.text`, `.data` e `.rodata` com checagem de limites de seção e de overflow de deslocamento 32-bit.

---

## 4. Layout do Executável Gerado (`ET_EXEC`)

O executável ELF64 dinâmico gerado pelo DCC possui:

- **Program Headers**: `PT_PHDR`, `PT_INTERP` (`/lib64/ld-linux-x86-64.so.2`), `PT_LOAD` (`R E` para código, `.rodata`, `.dynsym`, `.dynstr`, `.rela.plt`, `.plt`), `PT_LOAD` (`R W` separado para `.dynamic`, `.got.plt`, `.got`, `.data`, `.bss`), `PT_DYNAMIC` e `PT_GNU_STACK` (`RW`, não executável).
- **Zero páginas `RWE`**: código e dados vivem em segmentos `PT_LOAD` com permissões separadas, verificado automaticamente via `readelf -W -l`.
- **Section Headers completos** (13 seções + `.shstrtab`), auditados por `readelf -W -S`.
- **Bibliotecas dinâmicas**: `DT_NEEDED` para `libc.so.6` e, quando `-lm` é passado, `libm.so.6`.

---

## 5. Validações de Segurança em Entradas Binárias

`elf_leitor.delegua` valida rigorosamente todo `.o` e `.a` antes de indexar bytes:

- Magic `\x7fELF`, classe 64-bit, little-endian, tipo `ET_REL`, máquina `EM_X86_64`;
- `e_shoff`, `e_shentsize >= 64`, `e_shnum`, `e_shstrndx` dentro do arquivo;
- `sh_addralign <= 65536` e potência de 2 (evita explosão de memória por alinhamento hostil);
- `sh_offset + sh_size <= tamanhoArquivo` para seções `!= SHT_NOBITS`;
- Entradas de `.symtab` (`entsize >= 24`) e `.rela.*` (`entsize >= 24`) dentro dos limites da tabela e do `.strtab`;
- Assinatura `!<arch>\n`, cabeçalhos de 60 bytes e limites de tamanho de cada membro em archives `.a`.

---

## 6. Limitações Conhecidas do Linker

- Não gera bibliotecas compartilhadas (`-shared` / `ET_DYN`) nem executáveis PIE (`ET_DYN`).
- Não suporta `R_X86_64_TPOFF32` / TLS (`_Thread_local`/`__thread`), `IFUNC` customizado, scripts de linker GNU (`.ld`) ou `DT_RPATH`/`DT_RUNPATH`.
- Apenas `libc.so.6` e `libm.so.6` são vinculadas dinamicamente; outras `-l<nome>` são resolvidas como arquivos estáticos `lib<nome>.a` nos diretórios `-L` ou padrão do sistema.
