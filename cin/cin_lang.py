"""CIN dili: lexer + parser + CIN-32 kod ureteci.

Dil: 32-bit tamsayilar, diziler, if/else, while, fonksiyonlar (recursive),
gomululer: pixel(x,y,c), flush(), rand(seed?), arr(n), log(v), getpixel(x,y).

Kod uretimi: yigin makinesi. x1..x4 cirkin, x5=fp, x6=sp, x7=ra, x0=0/karsilastirma.
Cagri sozlesmesi: JAL ra'yi yigina iter; cagiran argumanlari TERSTEN push eder
(arg1 en ustte); callee epilogda argumanlari atar, sonucu push eder.
"""

import re

from .assembler import assemble
from .isa import DATA_BASE

TOKEN = re.compile(r"""
    (?P<num>\d+)
  | (?P<id>[A-Za-z_]\w*)
  | (?P<op>==|!=|<=|>=|\^|[-+*/%<>=!(){};,|&\[\]])
  | (?P<ws>\s+)
""", re.X)


def tokenize(src):
    src = re.sub(r"//[^\n]*", "", src)   # yorumlar
    toks, i = [], 0
    while i < len(src):
        m = TOKEN.match(src, i)
        if not m:
            raise SyntaxError(f"lexer tikandi @ {src[i:i + 20]!r}")
        i = m.end()
        if m.lastgroup != "ws":
            toks.append((m.lastgroup, m.group()))
    toks.append(("eof", ""))
    return toks


class P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def eat(self, val=None, kind=None):
        k, v = self.t[self.i]
        if val is not None and v != val:
            raise SyntaxError(f"{val!r} beklenirdi, {v!r} geldi")
        if kind is not None and k != kind:
            raise SyntaxError(f"{kind} beklenirdi, {v!r} geldi")
        self.i += 1
        return v

    def at(self, val):
        return self.t[self.i][1] == val

    def expr(self):
        node = self.xor_uz()
        while self.peek()[1] == "|":
            self.eat("|")
            node = ("or2", node, self.xor_uz())
        return node

    def xor_uz(self):
        node = self.cmp()
        while self.peek()[1] == "^":
            self.eat("^")
            node = ("xor2", node, self.cmp())
        return node

    def cmp(self):
        left = self.addsub()
        k, v = self.peek()
        if v in ("==", "!=", "<", ">", "<=", ">="):
            self.eat()
            return ("cmp", v, left, self.addsub())
        return left

    def addsub(self):
        node = self.muldiv()
        while self.peek()[1] in ("+", "-"):
            op = self.eat()
            node = ("bin", op, node, self.muldiv())
        return node

    def muldiv(self):
        node = self.unary()
        while self.peek()[1] in ("*", "/", "%"):
            op = self.eat()
            node = ("bin", op, node, self.unary())
        return node

    def unary(self):
        if self.at("-"):
            self.eat()
            return ("neg", self.unary())
        if self.at("!"):
            self.eat()
            return ("not", self.unary())
        return self.primary()

    def primary(self):
        k, v = self.peek()
        if k == "num":
            self.eat()
            return ("num", int(v))
        if v == "(":
            self.eat()
            e = self.expr()
            self.eat(")")
            return e
        if k == "id":
            self.eat()
            if self.at("("):
                self.eat("(")
                args = []
                if not self.at(")"):
                    args.append(self.expr())
                    while self.at(","):
                        self.eat(",")
                        args.append(self.expr())
                self.eat(")")
                return ("call", v, args)
            if self.at("["):
                self.eat("[")
                idx = self.expr()
                self.eat("]")
                return ("index", v, idx)
            return ("var", v)
        raise SyntaxError(f"beklenmedik {v!r}")

    def block(self):
        self.eat("{")
        stmts = []
        while not self.at("}"):
            stmts.append(self.stmt())
        self.eat("}")
        return ("block", stmts)

    def stmt(self):
        k, v = self.peek()
        if v == "let":
            self.eat("let")
            name = self.eat(kind="id")
            self.eat("=")
            e = self.expr()
            self.eat(";")
            return ("let", name, e)
        if v == "if":
            self.eat("if")
            self.eat("(")
            cond = self.expr()
            self.eat(")")
            then = self.block()
            els = None
            if self.at("else"):
                self.eat("else")
                els = self.block()
            return ("if", cond, then, els)
        if v == "while":
            self.eat("while")
            self.eat("(")
            cond = self.expr()
            self.eat(")")
            return ("while", cond, self.block())
        if v == "return":
            self.eat("return")
            e = None if self.at(";") else self.expr()
            self.eat(";")
            return ("return", e)
        if k == "id":
            if self.t[self.i + 1][1] == "=":
                name = self.eat(kind="id")
                self.eat("=")
                e = self.expr()
                self.eat(";")
                return ("assign", name, e)
            if self._dizi_atama():
                name = self.eat(kind="id")
                self.eat("[")
                idx = self.expr()
                self.eat("]")
                self.eat("=")
                e = self.expr()
                self.eat(";")
                return ("astore", name, idx, e)
        e = self.expr()
        self.eat(";")
        return ("exprstmt", e)

    def _dizi_atama(self):
        j = self.i + 1
        depth = 0
        while j < len(self.t):
            v = self.t[j][1]
            if v == "[":
                depth += 1
            elif v == "]":
                depth -= 1
                if depth == 0:
                    return self.t[j + 1][1] == "="
            elif depth == 0:
                return False
            j += 1
        return False

    def program(self):
        fns = []
        while self.peek()[0] != "eof":
            self.eat("fn")
            name = self.eat(kind="id")
            self.eat("(")
            params = []
            if not self.at(")"):
                params.append(self.eat(kind="id"))
                while self.at(","):
                    self.eat(",")
                    params.append(self.eat(kind="id"))
            self.eat(")")
            fns.append((name, params, self.block()))
        return fns


def parse(src):
    return P(tokenize(src)).program()


BUILTINS = {"pixel", "flush", "rand", "arr", "log", "getpixel"}


class Derleyici:
    def __init__(self):
        self.asm_lines = []
        self.labeln = 0
        self.globals = {}
        self.fns = {}
        self.locals = {}
        self.argc = 0

    def emit(self, line):
        self.asm_lines.append(line)

    def label(self, hint="L"):
        self.labeln += 1
        return f"_{hint}{self.labeln}"

    def push(self, r="x1"):
        self.emit(f"push {r}")

    def pop(self, r="x1"):
        self.emit(f"pop {r}")

    def kondey(self, cond):
        if cond[0] == "cmp":
            _, op, l, r = cond
            self.expr(l)
            self.expr(r)
            self.pop("x2")
            self.pop("x1")
            if op == "<":
                self.emit("slt x1, x1, x2")
            elif op == ">":
                self.emit("slt x1, x2, x1")
            elif op == "<=":
                self.emit("slt x1, x2, x1")
                self.emit("ldi x2, 1")
                self.emit("xor x1, x1, x2")
            elif op == ">=":
                self.emit("slt x1, x1, x2")
                self.emit("ldi x2, 1")
                self.emit("xor x1, x1, x2")
            elif op in ("==", "!="):
                self.emit("sub x1, x1, x2")
                self.emit("ldi x0, 0")
                self.emit("slt x2, x1, x0")
                self.emit("slt x3, x0, x1")
                self.emit("or x1, x2, x3")
                if op == "==":
                    self.emit("ldi x2, 1")
                    self.emit("xor x1, x1, x2")
            self.push("x1")
        else:
            self.expr(cond)
            self.pop("x1")
            self.emit("ldi x0, 0")
            self.emit("slt x2, x1, x0")
            self.emit("slt x3, x0, x1")
            self.emit("or x1, x2, x3")
            self.push("x1")

    def expr(self, node):
        t = node[0]
        if t == "num":
            v = node[1] & 0xFFFFFFFF
            v = v - (1 << 32) if v >= (1 << 31) else v
            if -32768 <= v <= 65535:
                self.emit(f"ldi x1, {v & 0xFFFF}")
            else:
                self.emit(f"ldi x1, {v & 0xFFFF}")
                self.emit(f"ldi x2, {(v >> 16) & 0xFFFF}")
                self.emit("ldi x3, 16")
                self.emit("shl x2, x2, x3")
                self.emit("or x1, x1, x2")
            self.push("x1")
        elif t == "var":
            self._var_adres(node[1])
            self.emit("ld x1, x1, x0")
            self.push("x1")
        elif t == "index":
            self._dizi_adres(node[1], node[2])
            self.emit("ld x1, x1, x0")
            self.push("x1")
        elif t == "bin":
            _, op, l, r = node
            self.expr(l)
            self.expr(r)
            self.pop("x2")
            self.pop("x1")
            self.emit({"+" : "add", "-": "sub", "*": "mul",
                       "/": "div", "%": "mod"}[op] + " x1, x1, x2")
            self.push("x1")
        elif t == "neg":
            self.expr(node[1])
            self.emit("ldi x2, 0")
            self.pop("x1")
            self.emit("sub x1, x2, x1")
            self.push("x1")
        elif t == "not":
            self.kondey(node[1])
            self.pop("x1")
            self.emit("ldi x2, 1")
            self.emit("xor x1, x1, x2")
            self.push("x1")
        elif t == "xor2":
            self.expr(node[1])
            self.expr(node[2])
            self.pop("x2")
            self.pop("x1")
            self.emit("xor x1, x1, x2")
            self.push("x1")
        elif t == "or2":
            self.expr(node[1])
            self.expr(node[2])
            self.pop("x2")
            self.pop("x1")
            self.emit("or x1, x1, x2")
            self.push("x1")
        elif t == "cmp":
            self.kondey(node)
        elif t == "call":
            self._call(node[1], node[2])
        else:
            raise RuntimeError(f"ifade? {t}")

    def _var_adres(self, name):
        if name in self.globals:
            self.emit(f"ldi x1, {self.globals[name]}")
        elif name in self.locals:
            self.emit("mov x1, x5")
            self.emit(f"ldi x3, {self.locals[name] & 0xFFFF}")
            self.emit("add x1, x1, x3")
        else:
            raise NameError(f"tanimsiz degisken {name!r}")

    def _dizi_adres(self, name, idx_node):
        """x1 = ptr + idx. Yuva adresi OKUNUP gostericisi yuklenir; her ikisi
        de aradaki ifadelerden yigin uzerinde korunur."""
        self._var_adres(name)
        self.emit("ld x1, x1, x0")     # yuvadaki gostericinin degeri
        self.push("x1")                # gostericisi yiginda sakla
        self.expr(idx_node)
        self.pop("x3")                 # idx
        self.pop("x2")                 # ptr
        self.emit("add x2, x2, x3")
        self.emit("mov x1, x2")

    def _call(self, name, args):
        if name in BUILTINS:
            self._builtin(name, args)
            return
        if name not in self.fns:
            raise NameError(f"bilinmeyen fonksiyon {name!r}")
        for a in reversed(args):
            self.expr(a)
        self.emit(f"jal f_{name}")
        self.pop("x1")
        self.push("x1")

    def _builtin(self, name, args):
        if name == "pixel":
            for a in args:
                self.expr(a)
            self.pop("x3")
            self.pop("x2")
            self.pop("x1")
            self.emit("syscall 1")
            self.push("x0")
        elif name == "flush":
            self.emit("syscall 2")
            self.push("x0")
        elif name == "rand":
            if args:
                self.expr(args[0])
                self.pop("x1")
            else:
                self.emit("ldi x1, 0")
            self.emit("syscall 3")
            self.push("x4")
        elif name == "arr":
            self.expr(args[0])
            self.pop("x1")
            self.emit("syscall 5")
            self.push("x4")
        elif name == "getpixel":
            self.expr(args[0])
            self.pop("x1")
            self.expr(args[1])
            self.pop("x2")
            self.emit("syscall 6")
            self.push("x4")
        elif name == "log":
            self.expr(args[0])
            self.pop("x1")
            self.emit("syscall 4")
            self.push("x0")

    def stmt(self, node):
        t = node[0]
        if t == "block":
            for s in node[1]:
                self.stmt(s)
        elif t == "exprstmt":
            self.expr(node[1])
            self.pop("x2")
        elif t == "let":
            self._store(node[1], node[2])
        elif t == "assign":
            self._store(node[1], node[2])
        elif t == "astore":
            _, name, idx, e = node
            self._dizi_adres(name, idx)
            self.push("x1")            # adresi sakla
            self.expr(e)
            self.pop("x1")             # deger
            self.pop("x2")             # adres
            self.emit("st x2, x0, x1")
        elif t == "if":
            _, cond, then, els = node
            self.kondey(cond)
            self.pop("x1")
            self.emit("ldi x0, 0")
            l_else = self.label("else")
            self.emit(f"beq x1, {l_else}")
            self.stmt(then)
            if els:
                l_end = self.label("endif")
                self.emit(f"jmp {l_end}")
                self.emit(f"{l_else}:")
                self.stmt(els)
                self.emit(f"{l_end}:")
            else:
                self.emit(f"{l_else}:")
        elif t == "while":
            _, cond, body = node
            l_top = self.label("while")
            l_end = self.label("wend")
            self.emit(f"{l_top}:")
            self.kondey(cond)
            self.pop("x1")
            self.emit("ldi x0, 0")
            self.emit(f"beq x1, {l_end}")
            self.stmt(body)
            self.emit(f"jmp {l_top}")
            self.emit(f"{l_end}:")
        elif t == "return":
            if node[1] is not None:
                self.expr(node[1])
                self.pop("x1")
            else:
                self.emit("ldi x1, 0")
            self._epilog(self.argc)
        else:
            raise RuntimeError(f"deyim? {t}")

    def _store(self, name, e):
        self.expr(e)
        self.pop("x2")
        self._var_adres(name)
        self.emit("st x1, x0, x2")

    def _epilog(self, argc):
        self.emit("mov sp, x5")
        self.emit("pop x5")
        self.emit("pop ra")
        for _ in range(argc):
            self.emit("pop x2")
        self.emit("push x1")
        self.emit("jr")

    def fn(self, name, params, body):
        self.argc = len(params)
        self.locals = {}
        self.emit(f"f_{name}:")
        self.emit("push x5")
        self.emit("mov x5, sp")

        bulunan = []
        def tara(n):
            if n[0] == "let":
                if n[1] not in self.globals and n[1] not in params \
                        and n[1] not in self.locals and n[1] not in bulunan:
                    bulunan.append(n[1])
            elif n[0] == "block":
                for s in n[1]:
                    tara(s)
            elif n[0] == "if":
                tara(n[2])
                if n[3]:
                    tara(n[3])
            elif n[0] == "while":
                tara(n[2])
        tara(body)
        if len(bulunan) > 120:
            raise RuntimeError(f"{name}: yerel cerceve 120 sozcuktu asti")
        for i, nm in enumerate(bulunan):
            self.locals[nm] = -1 - i
        for i, p in enumerate(params):
            self.locals[p] = 2 + i

        if bulunan:
            self.emit("ldi x1, 0")
            for _ in bulunan:
                self.emit("push x1")
        self.stmt(body)
        self.emit("ldi x1, 0")
        self._epilog(len(params))


def _kaydet_globals(d, body):
    if body[0] == "block":
        for s in body[1]:
            if s[0] == "let" and s[1].startswith("g_") and s[1] not in d.globals:
                d.globals[s[1]] = d.gaddr
                d.gaddr += 1


def derle(src):
    fns = parse(src)
    d = Derleyici()
    for name, params, body in fns:
        d.fns[name] = params
    for name, params, body in fns:
        _kaydet_globals(d, body)
    d.emit("jal f_main")
    d.emit("halt")
    for name, params, body in fns:
        d.fn(name, params, body)
    return assemble("\n".join(d.asm_lines))
