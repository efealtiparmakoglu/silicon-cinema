"""CIN-32: sözcük adresli, 32-bit, sabit formatlı toy ISA.

Her komut TAM 2 sözcük:
    sözcük 0: [op:8 | a:8]
    sözcük 1: [b:8 | c:8]  veya  [imm:16]

Dallanmalar tek yazmacı x0 ile karşılaştırır (derleyici taşırma yapar):
    BEQ a, off  ->  x[a] == x[0] ise dallan

Yazmaçlar: x0..x5 genel, x6 = sp, x7 = ra (ret).

Bellek haritası (sözcük adresli, 2^16 sözcük):
    0x0000 kod      0x4000 global değişkenler
    0x7000 yığın    0x8000 framebuffer (RGB565)     0xC000 heap
"""

MASK = 0xFFFFFFFF
FB_W, FB_H = 128, 72
FB_BASE = 0x8000
STACK_TOP = 0x7000
HEAP_BASE = 0xC000
DATA_BASE = 0x4000
MEM_WORDS = 1 << 16

OPS = {
    "NOP": 0x00, "LDI": 0x01, "MOV": 0x02,
    "ADD": 0x10, "SUB": 0x11, "MUL": 0x12, "DIV": 0x13,
    "XOR": 0x14, "OR": 0x15, "AND": 0x16,
    "MOD": 0x1A, "SHL": 0x17, "SHR": 0x18, "SLT": 0x19,
    "LD": 0x20, "ST": 0x21,
    "BEQ": 0x30, "BNE": 0x31, "BLT": 0x32,
    "JAL": 0x40, "JR": 0x41, "JMP": 0x42,
    "PUSH": 0x50, "POP": 0x51,
    "SYSCALL": 0x60, "HALT": 0x70,
}
OPNAMES = {v: k for k, v in OPS.items()}

SP, RA = 6, 7


def s32(v):
    v &= MASK
    return v - (1 << 32) if v >= (1 << 31) else v


def enc(op, a=0, b=0, c=0):
    return ((OPS[op] & 0xFF) << 8 | (a & 0xFF), (b & 0xFF) << 8 | (c & 0xFF))


def enc_imm(op, a, imm):
    return ((OPS[op] & 0xFF) << 8 | (a & 0xFF), imm & 0xFFFF)


def s16(v):
    v &= 0xFFFF
    return v - (1 << 16) if v >= (1 << 15) else v


class CPU:
    """CIN-32 emülatörü. frames = flush() ile yakalanan kareler."""

    def __init__(self, code):
        self.mem = [0] * MEM_WORDS
        for i, w in enumerate(code):
            self.mem[i] = w & MASK
        self.x = [0] * 8
        self.x[SP] = STACK_TOP
        self.pc = 0
        self.halted = False
        self.frames = []
        self.log = []            # syscall 4 çıktıları
        self.rng = 0x9E3779B9
        self.cycles = 0
        self.heap = HEAP_BASE

    @property
    def sp(self):
        return self.x[SP]

    @property
    def ra(self):
        return self.x[RA]

    def _syscall(self, fn):
        x = self.x
        if fn == 1:      # pixel(x=x1, y=x2, c=x3)
            px, py, c = x[1] % FB_W, x[2] % FB_H, x[3] & 0xFFFF
            self.mem[FB_BASE + py * FB_W + px] = c
        elif fn == 2:    # flush
            self.frames.append(self.mem[FB_BASE:FB_BASE + FB_W * FB_H])
        elif fn == 3:    # rand(seed?) -> x0
            if x[1]:
                self.rng = x[1] & MASK
            r = self.rng
            r ^= (r << 13) & MASK
            r ^= r >> 17
            r ^= (r << 5) & MASK
            self.rng = r & MASK
            x[4] = self.rng
        elif fn == 4:    # debug: log'a x1 yaz
            self.log.append(s32(x[1]))
        elif fn == 5:    # alloc(n=x1) -> x4 (sözcük dizisi, heap bump)
            x[4] = self.heap
            self.heap += x[1]
        elif fn == 6:    # getpixel(x=x1, y=x2) -> x4
            px, py = x[1] % FB_W, x[2] % FB_H
            x[4] = self.mem[FB_BASE + py * FB_W + px]
        else:
            raise RuntimeError(f"bilinmeyen syscall {fn}")

    def step(self):
        w0, w1 = self.mem[self.pc], self.mem[self.pc + 1]
        op, a = w0 >> 8, w0 & 0xFF
        b, c = w1 >> 8, w1 & 0xFF
        imm = s16(w1)
        x = self.x
        self.pc += 2
        self.cycles += 1
        if op == OPS["NOP"]:
            pass
        elif op == OPS["LDI"]:
            x[a] = s32(imm & 0xFFFF)  # işaretsiz 16-bit (adresler için)
        elif op == OPS["MOV"]:
            if a > 7 or b > 7:
                raise RuntimeError(
                    f"MOV bozuk yazmac a={a} b={b} @ pc={self.pc - 2:#x} "
                    f"(mem[{self.pc - 4:#x}]={self.mem[self.pc - 4]:#x})")
            x[a] = x[b]
        elif op == OPS["ADD"]:
            x[a] = s32(x[b] + x[c])
        elif op == OPS["SUB"]:
            x[a] = s32(x[b] - x[c])
        elif op == OPS["MUL"]:
            x[a] = s32(x[b] * x[c])
        elif op == OPS["DIV"]:
            x[a] = s32(cdiv(x[b], x[c]))
        elif op == OPS["MOD"]:
            x[a] = s32(cmod(x[b], x[c]))
        elif op == OPS["XOR"]:
            x[a] = x[b] ^ x[c]
        elif op == OPS["OR"]:
            x[a] = x[b] | x[c]
        elif op == OPS["AND"]:
            x[a] = x[b] & x[c]
        elif op == OPS["SHL"]:
            x[a] = s32(x[b] << (x[c] & 31))
        elif op == OPS["SHR"]:
            x[a] = (x[b] & MASK) >> (x[c] & 31)
        elif op == OPS["SLT"]:
            x[a] = 1 if x[b] < x[c] else 0
        elif op == OPS["LD"]:
            x[a] = s32(self.mem[(x[b] + x[c]) & 0xFFFF])
        elif op == OPS["ST"]:
            _ad = (x[a] + x[b]) & 0xFFFF
            if _ad < 0x800:
                raise RuntimeError(f"WILD STORE @ pc={self.pc - 2:#x} addr={_ad:#x} val={x[c]}")
            self.mem[_ad] = x[c] & MASK
        elif op == OPS["BEQ"]:
            if x[a] == x[0]:
                self.pc += imm * 2
        elif op == OPS["BNE"]:
            if x[a] != x[0]:
                self.pc += imm * 2
        elif op == OPS["BLT"]:
            if x[a] < x[0]:
                self.pc += imm * 2
        elif op == OPS["JAL"]:
            # ra'yi yigina it + yazmaca koy (recursion guvenli cagri sozlesmesi)
            x[SP] = (x[SP] - 1) & 0xFFFF
            self.mem[x[SP]] = self.pc & MASK
            x[RA] = self.pc
            self.pc += imm * 2
        elif op == OPS["JMP"]:
            self.pc += imm * 2
        elif op == OPS["JR"]:
            self.pc = x[RA] & MASK
        elif op == OPS["PUSH"]:
            x[SP] = (x[SP] - 1) & 0xFFFF
            self.mem[x[SP]] = x[a] & MASK
        elif op == OPS["POP"]:
            x[a] = s32(self.mem[x[SP]])
            x[SP] = (x[SP] + 1) & 0xFFFF
        elif op == OPS["SYSCALL"]:
            self._syscall(a)
        elif op == OPS["HALT"]:
            self.halted = True
        else:
            raise RuntimeError(f"bozuk opcode {op:#x} @ {self.pc - 2:#x}")

    def run(self, max_cycles=400_000_000):
        while not self.halted and self.cycles < max_cycles:
            self.step()
        if not self.halted:
            raise RuntimeError("cycles tükendi (sonsuz döngü?)")
        return self


def cdiv(a, b):
    """C tarzi bolme: sifira dogru kes, 0'a bolme -> 0."""
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def cmod(a, b):
    if b == 0:
        return 0
    return a - cdiv(a, b) * b


def xorshift(state):
    """syscall 3'ün birebir Python kopyası (diferansiyel test için)."""
    r = state & MASK
    r ^= (r << 13) & MASK
    r ^= r >> 17
    r ^= (r << 5) & MASK
    return r & MASK
