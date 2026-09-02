# RED2 Strict Primitive Firing, Integer ADD First — Task 4

**Target:** Implement strict primitive fire path for integer ADD (`(Add m n)`).

**Architecture:** The primitive-fire mechanism uses `prim` register (primitive opcode) and `fire` register (countdown). When a head primitive with `q > 0` is applied to reduced arguments, it fires — executing the primitive and replacing the graph.

**Fire Path:**
1. On forward APP with `prim` set and `q > 0`: decrement fire, continue reduction
2. On reaching `fire == 0` with `q == 0`: execute primitive, write result, reclaim memory
3. For ADD: `(Add m n)` with `m,n` reduced → `m + n` (integer)

**Chapter 4 Behavior:**
- ADD is a binary (`PRIM_2`) strict primitive
- When `q > 0`, APP with primitive argument copies to graph (passive)
- When `q == 0` and APP argument is reduced primitive, fires
- Fire replaces APP+ARG with result, reclaims ARG address

**States to Track:**
- `prim`: primitive identifier (0=ADD, 1=SUB, etc.)
- `fire`: countdown to active execution (0 = ready to fire)
- `argcnt`: arguments collected (unused initially, for Task 3)

**Integer ADD Semantics:**
- Input: two reduced integers m, n
- Output: single INT word with `m + n`
- Memory: APP/ARG words reclaimed (overwritten by STOP/result)
- q=0 preserved (no quantum consumption for the operation itself)
