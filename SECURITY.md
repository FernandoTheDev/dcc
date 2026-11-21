# Política de Segurança — DCC (Delégua C Compiler)

## Estado de Maturidade

O **DCC (Delégua C Compiler)** é um projeto **experimental em desenvolvimento ativo** (v0.2.0), desenvolvido com forte assistência e geração de código por inteligência artificial (ver [docs/AI_DEVELOPMENT.md](docs/AI_DEVELOPMENT.md)).

- O DCC **não** passou por auditoria formal independente de segurança.
- O DCC **não** deve ser considerado livre de vulnerabilidades nem recomendado para compilação desassistida de entradas não confiáveis em ambientes sensíveis ou de produção crítica.

---

## Modelo de Ameaça e Superfícies de Ataque

Todo compilador processa entradas complexas e potencialmente hostis:

1. **Arquivos-fonte `.c` e cabeçalhos `.h`** (macro bombs, `#include` cíclico, aninhamento profundo de `#if`/expressões/parênteses, comentários e literais não terminados, bytes arbitrários).
2. **Argumentos de linha de comando e caminhos de arquivo** (flags malformadas, nomes de arquivo com espaços ou metacaracteres de shell).
3. **Arquivos binários de entrada do linker (`.o` ELF64 e `.a` GNU `ar`)** (cabeçalhos truncados, magic/endianness/classe inválidos, `e_shoff`/`sh_offset`/`sh_size` fora dos limites, `sh_addralign` gigantes ou não potência de 2, índices de símbolos/seções fora da faixa, relocações fora da seção ou com overflow de 32 bits).
4. **Código C compilado**: o compilador pode gerar código incorreto em recursos C99 ainda incompletos ou casos de borda; o binário gerado executa com os mesmos privilégios do usuário que o invoca.

---

## Medidas de Endurecimento Implementadas (v0.2.0)

O Ciclo III introduziu proteções concretas e testadas contra falhas comuns de parsers e linkers:

- **Pré-processador**:
  - Limite de profundidade de `#include` (`64`, código `E1002`) e total de inclusões por TU (`2048`).
  - Limite de aninhamento de `#if` (`256`, `E1003`) e profundidade de expressão `#if` (`128`, `E1005`).
  - Limite de profundidade de macro (`128`), total de expansões (`50.000`) e limite de tokens expandidos (`50.000`/linha, `400.000`/TU — `E1011`) contra expansão exponencial (*billion laughs* de macros).
  - Proteção contra divisão por zero (`E1006`), `INT64_MIN / -1` e shifts negativos/≥64 em `#if`.
  - Detecção de comentários `/*` não fechados (`E1001`) e validação de `##` no início/fim de macro (`E1014`).
  - Descoberta de cabeçalhos do sistema via `Processo.executar("find", ...)` sem invocação de `/bin/sh`.
- **Lexer e Parser**:
  - Precedence Climbing em expressões binárias e limite de profundidade recursiva (`96`, `E2010`) prevenindo estouro de pilha do runtime CGD em entradas profundamente aninhadas.
  - Verificação de limites ao avançar tokens e encerramento controlado de strings/caracteres/comentários malformados (`E2001`–`E2005`).
- **Semântica e IR**:
  - Limite de tamanho de array (`1 GiB`, `E3004`) contra overflow de cálculo de layout.
  - Verificador estrutural da IR SSA (`src/ir/ir_verify.delegua`) executado antes do backend, rejeitando registradores indefinidos, blocos vazios, terminadores ausentes/duplicados e índices fora da faixa (`E4001`).
- **Backend, I/O e Linker**:
  - Verificação de alcance `rel32` e existência de rótulos em `emissor.delegua`, e guarda de tamanho de frame de pilha em `codegen.delegua`.
  - Remoção de interpolação de caminhos em comandos shell de I/O binário (uso de `chmod` via FFI `libc` e passagem de caminho por argumento posicional `$1` sem expansão de variáveis).
  - Validação completa de cabeçalhos ELF64 e archives `.a` em `src/linker/elf_leitor.delegua` (magic, classe 64-bit, little-endian, `ET_REL`, limites de seções/tabelas, `sh_addralign <= 65536` potência de 2, bounds de símbolos e relocações).
  - Verificação de bounds e overflow de 32 bits ao aplicar relocações em `src/linker/linker.delegua`.

Estas defesas são testadas automaticamente em `tests/test_security_fuzz.py` (12 casos adversariais de pré-processador, 50 entradas fuzzing/malformadas para lexer/parser e 15 binários ELF64/ar hostis).

---

## Limitações de Segurança Conhecidas

1. **Dependência de `base64` para I/O binário**: enquanto o runtime FFI do CGD não expõe leitura/escrita binária direta de `Bytes` em arquivo, o driver invoca `base64` via `cgd:processo` (com comando fixo e caminho em argumento posicional, sem interpolação).
2. **Sem sandboxing interno**: o DCC não aplica `seccomp`, `rlimit` ou namespaces por conta própria. Ao compilar código C não confiável (ou ao executar binários produzidos), utilize isolamento externo (contêiner, `ulimit`, máquina virtual ou usuário sem privilégios).
3. **Sem mitigações avançadas no código gerado**: os executáveis gerados pelo DCC ainda não emitem *stack canaries* (`-fstack-protector`), `RELRO`/`BIND_NOW` completo ou CFI, embora emitam `.note.GNU-stack` não-executável e segmentos `PT_LOAD` separados (`R E` e `R W`, sem páginas `RWE`).
4. **Cobertura de fuzzing finita**: a suíte `tests/test_security_fuzz.py` executa casos determinísticos e 50 entradas pseudoaleatórias por execução; isso reduz regressões óbvias, mas não substitui fuzzing contínuo de longa duração (AFL++/libFuzzer).

---

## Como Reportar Vulnerabilidades

Se você encontrar um crash, loop infinito, corrupção de memória, geração incorreta de código com impacto de segurança ou falha de validação no linker/parser do DCC:

1. **Não publique exploits destrutivos antes da análise**, quando aplicável.
2. **Abra um reporte através do canal de segurança ou issue tracker do repositório onde o DCC estiver hospedado**, incluindo:
   - Versão do DCC (`dcc --version`) e versão do CGD (`cgd --versao`);
   - Arquivo mínimo de reprodução (`.c`, `.h`, `.o` ou `.a`) e linha de comando exata;
   - Saída completa (`stdout`, `stderr` e código de retorno);
   - Impacto observado (ex.: crash do compilador, hang, código incorreto silencioso).
3. Evite incluir dados sensíveis ou credenciais nos arquivos de reprodução.
