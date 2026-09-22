"""CIN-32 assembler: metin -> makine sözcükleri.

    etiket:
    add x1, x2, x3          # reg-reg (add sub mul div xor or and shl shr slt)
    ldi x1, 100 | 0x8000    # 16-bit işaretsiz anlık değer
    ldi x1, etiket          # etiketin mutlak adresi
    mov x1, x2
    ld x1, x2, 4            # x1 = mem[x2 + 4]
    st x2, 4, x3            # mem[x2 + 4] = x3
    beq/bne/blt x1, etiket  # x1'i x0 ile karşılaştırır
    jal etiket / jr         # çağır / geri dön (x7 = ra)
    push x1 / pop x1
    syscall 3 / halt / nop
"""

import re

from .isa import OPS, enc, enc_imm

REG = {"sp": 6, "ra": 7}
REL_OPS = {"beq": "BEQ", "bne": "BNE", "blt": "BLT"}
RR_OPS = {"add": "ADD", "sub": "SUB", "mul": "MUL", "div": "DIV",
          "mod": "MOD", "xor": "XOR", "or": "OR", "and": "AND",
          "shl": "SHL", "shr": "SHR", "slt": "SLT"}


def _reg(tok):
    tok = tok.strip()
    if tok in REG:
        return REG[tok]
    if re.fullmatch(r"x[0-5]", tok):
        return int(tok[1])
    raise SyntaxError(f"yazmaç değil: {tok!r} (x0..x5, sp, ra)")


def _num(tok):
    return int(tok, 0)


def assemble(text):
    """(words, labels) — dallanmalar sözcük cinsinden göreli, LDI etiketi mutlak."""
    lines = [ln.split("#")[0].strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]

    labels, fixups, words = {}, [], []
    for line in lines:
        while True:
            m = re.match(r"^([A-Za-z_]\w*):\s*(.*)$", line)
            if not m:
                break
            labels[m.group(1)] = len(words)
            line = m.group(2)
        if not line:
            continue
        parts = line.split(None, 1)
        op = parts[0].lower()
        args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []

        if op == ".word":
            words.append(_num(args[0]) & 0xFFFFFFFF)
        elif op in ("halt", "nop", "jr"):
            words += enc("HALT" if op == "halt" else "NOP" if op == "nop" else "JR")
        elif op == "jmp":
            fixups.append((len(words) + 1, "rel", args[0]))
            words += enc_imm("JMP", 0, 0)
        elif op == "jal":
            fixups.append((len(words) + 1, "rel", args[0]))
            words += enc_imm("JAL", 0, 0)
        elif op in REL_OPS:
            fixups.append((len(words) + 1, "rel", args[1]))
            words += enc_imm(REL_OPS[op], _reg(args[0]), 0)
        elif op == "ldi":
            a = _reg(args[0])
            if re.fullmatch(r"-?\d+|0[xX][0-9a-fA-F]+", args[1]):
                words += enc_imm("LDI", a, _num(args[1]))
            else:
                fixups.append((len(words) + 1, "abs", args[1]))
                words += enc_imm("LDI", a, 0)
        elif op == "mov":
            words += enc("MOV", _reg(args[0]), _reg(args[1]))
        elif op in RR_OPS:
            words += enc(RR_OPS[op], _reg(args[0]), _reg(args[1]), _reg(args[2]))
        elif op in ("ld", "st"):
            # ld x1, x2, x3 -> x1 = mem[x2+x3]  |  st x1, x2, x3 -> mem[x1+x2] = x3
            words += enc("LD" if op == "ld" else "ST",
                         _reg(args[0]), _reg(args[1]), _reg(args[2]))
        elif op in ("push", "pop"):
            words += enc("PUSH" if op == "push" else "POP", _reg(args[0]))
        elif op == "syscall":
            words += enc("SYSCALL", _num(args[0]))
        else:
            raise SyntaxError(f"anlaşılamayan komut: {line!r}")

    for idx, tip, et in fixups:
        if et not in labels:
            raise NameError(f"etiket bulunamadı: {et!r}")
        if tip == "rel":      # pc kurmadan sonraki komut idx+1'de; imm = (hedef - idx-1)/2
            words[idx] = ((labels[et] - idx - 1) // 2) & 0xFFFF
        else:
            words[idx] = labels[et] & 0xFFFF
    return words, labels
