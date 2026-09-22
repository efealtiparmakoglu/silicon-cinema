"""CIN referans yorumlayicisi — derleyici + CPU ile diferansiyel dogrulama
icin BIREBIR ayni semantik: 32-bit sarmalama, sifira bolme -> 0, C kalani,
xorshift32 RNG, RGB565 framebuffer.
"""

from .isa import FB_H, FB_W, MASK, cdiv, cmod, xorshift


class Donus(Exception):
    pass


class Dizi(list):
    def __init__(self, n):
        super().__init__([0] * n)


def s32w(v):
    v &= MASK
    return v - (1 << 32) if v >= (1 << 31) else v


class Kirm:
    def __init__(self, fns, seed=0x9E3779B9):
        self.fns = {name: (params, body) for name, params, body in fns}
        self.globals = {}
        self.frames = []
        self.log = []
        self.fb = [[0] * FB_W for _ in range(FB_H)]
        self.rng = seed

    def _pixel(self, a):
        x, y, c = int(a[0]), int(a[1]), int(a[2]) & 0xFFFF
        self.fb[y % FB_H][x % FB_W] = c

    def _flush(self):
        self.frames.append([row[:] for row in self.fb])

    def _rand(self, a):
        if a and a[0]:
            self.rng = int(a[0]) & MASK
        self.rng = xorshift(self.rng)
        return s32w(self.rng)

    def deger(self, node, env):
        t = node[0]
        if t == "num":
            return s32w(node[1])
        if t == "var":
            name = node[1]
            if name in env:
                return env[name]
            return self.globals[name]
        if t == "index":
            arr = self.deger(("var", node[1]), env)
            i = self.deger(node[2], env)
            return arr[int(i) % len(arr)]
        if t == "bin":
            a = self.deger(node[2], env)
            b = self.deger(node[3], env)
            op = node[1]
            if op == "+":
                r = (a + b) & MASK
            elif op == "-":
                r = (a - b) & MASK
            elif op == "*":
                r = (a * b) & MASK
            elif op == "/":
                r = cdiv(a, b) & MASK
            elif op == "%":
                r = cmod(a, b) & MASK
            else:
                raise RuntimeError(op)
            return s32w(r)
        if t == "neg":
            return s32w(-self.deger(node[1], env))
        if t == "not":
            return 0 if self.deger(node[1], env) != 0 else 1
        if t == "xor2":
            return self.deger(node[1], env) ^ self.deger(node[2], env)
        if t == "or2":
            return self.deger(node[1], env) | self.deger(node[2], env)
        if t == "cmp":
            a = self.deger(node[2], env)
            b = self.deger(node[3], env)
            op = node[1]
            sonuc = {"==": a == b, "!=": a != b, "<": a < b,
                     ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            return 1 if sonuc else 0
        if t == "call":
            return self.cagir(node[1], node[2], env)
        raise RuntimeError(f"ifade? {t}")

    def cagir(self, name, args_nodes, env):
        if name == "pixel":
            self._pixel([self.deger(a, env) for a in args_nodes])
            return 0
        if name == "flush":
            self._flush()
            return 0
        if name == "rand":
            return self._rand([self.deger(a, env) for a in args_nodes])
        if name == "arr":
            n = self.deger(args_nodes[0], env)
            return Dizi(int(n))
        if name == "getpixel":
            x = int(self.deger(args_nodes[0], env))
            y = int(self.deger(args_nodes[1], env))
            return self.fb[y % FB_H][x % FB_W]
        if name == "log":
            self.log.append(self.deger(args_nodes[0], env))
            return 0
        if name not in self.fns:
            raise NameError(f"bilinmeyen fonksiyon {name!r}")
        params, body = self.fns[name]
        degerler = [self.deger(a, env) for a in args_nodes]
        yeni = dict(zip(params, degerler))
        try:
            self.calis(body, yeni)
        except Donus:
            pass
        return yeni.get("__ret", 0)

    def calis(self, node, env):
        t = node[0]
        if t == "block":
            for s in node[1]:
                self.calis(s, env)
        elif t == "let":
            env[node[1]] = self.deger(node[2], env)
        elif t == "assign":
            env[node[1]] = self.deger(node[2], env)
        elif t == "astore":
            arr = self.deger(("var", node[1]), env)
            arr[int(self.deger(node[2], env)) % len(arr)] = self.deger(node[3], env)
        elif t == "if":
            if self.deger(node[1], env) != 0:
                self.calis(node[2], env)
            elif node[3]:
                self.calis(node[3], env)
        elif t == "while":
            while self.deger(node[1], env) != 0:
                self.calis(node[2], env)
        elif t == "return":
            env["__ret"] = self.deger(node[1], env) if node[1] else 0
            raise Donus
        elif t == "exprstmt":
            self.deger(node[1], env)
        else:
            raise RuntimeError(f"deyim? {t}")

    def kos(self):
        if "main" in self.fns:
            self.cagir("main", [], {})
