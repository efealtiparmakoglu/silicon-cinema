#!/usr/bin/env python3
"""Fuzzer: rastgele CIN programlari uretir, yorumlayici ile derlenmis+CPU
sonucunu karsilastirir. Herhangi bir sapma -> derleyicide bug.

Kural: tum programlar sonlu calisir (while sadece sayac kalibiyla kurulur).
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cin.cin_lang import derle, parse
from cin.isa import CPU
from cin.interp import Kirm


class Uretici:
    def __init__(self, rng):
        self.r = rng
        self.n = 0

    def yeni_ad(self, onek):
        self.n += 1
        return f"{onek}{self.n}"

    def ifade(self, havuz, derinlik=0):
        r = self.r
        secim = r.random()
        if derinlik > 3 or secim < 0.3 or not havuz:
            return str(r.randint(0, 97))
        if secim < 0.55:
            op = r.choice(["+", "-", "*"])
            return f"({self.ifade(havuz, derinlik+1)} {op} {self.ifade(havuz, derinlik+1)})"
        if secim < 0.7:
            op = r.choice(["/", "%"])
            return f"({self.ifade(havuz, derinlik+1)} {op} {r.randint(1, 13)})"
        if secim < 0.85:
            return f"({self.ifade(havuz, derinlik+1)} < {self.ifade(havuz, derinlik+1)})"
        return r.choice(havuz)

    def deyim(self, havuz, girinti=2):
        r = self.r
        h = " " * girinti
        secim = r.random()
        if secim < 0.3 and havuz:
            return f"{h}{r.choice(havuz)} = {self.ifade(havuz)};"
        if secim < 0.5:
            ad = self.yeni_ad("v")
            satir = f"{h}let {ad} = {self.ifade(havuz)};"
            return satir + "\n" + f"{h}log({ad});"
        if secim < 0.7:
            return (f"{h}if ({self.ifade(havuz)} < {self.ifade(havuz)}) {{\n"
                    f"{h}  log({self.ifade(havuz)});\n"
                    f"{h}}}")
        # sinirli dongu kalibi: sayac 0'dan K'ya
        c = self.yeni_ad("c")
        k = r.randint(2, 10)
        ic = []
        for _ in range(r.randint(1, 2)):
            ad = self.yeni_ad("w")
            ic.append(f"{h}  let {ad} = {self.ifade(havuz + [c])};")
            ic.append(f"{h}  log({ad});")
        govde = "\n".join(ic) if ic else f"{h}  log({c});"
        return (f"{h}let {c} = 0;\n"
                f"{h}while ({c} < {k}) {{\n"
                f"{govde}\n"
                f"{h}  {c} = {c} + 1;\n"
                f"{h}}}")

    def fonksiyon(self):
        r = self.r
        ad = self.yeni_ad("fn")
        nparam = r.randint(1, 2)
        params = [self.yeni_ad("p") for _ in range(nparam)]
        havuz = list(params)
        govde = []
        for _ in range(r.randint(2, 4)):
            govde.append(self.deyim(havuz, 2))
        son = self.yeni_ad("s")
        govde.append(f"  let {son} = {self.ifade(havuz)};")
        govde.append(f"  return {son};")
        return (f"fn {ad}({', '.join(params)}) {{\n" + "\n".join(govde) + "\n}\n",
                ad, son, nparam)


def program_uret(rng):
    u = Uretici(rng)
    parcalar = []
    cagrilar = []
    for _ in range(rng.randint(1, 3)):
        metin, ad, son, nparam = u.fonksiyon()
        parcalar.append(metin)
        arglar = ", ".join(str(rng.randint(0, 40)) for _ in range(nparam))
        cagrilar.append(f"  log({ad}({arglar}) % 1000);")
    main_govde = "\n".join(cagrilar)
    for _ in range(rng.randint(1, 3)):
        main_govde += "\n" + u.deyim(["m1", "m2"], 2)
    main = "fn main() {\n  let m1 = 3;\n  let m2 = 7;\n" + main_govde + "\n}"
    return "\n".join(parcalar) + "\n" + main


def bir_test(idx, rng):
    src = program_uret(rng)
    try:
        words, _ = derle(src)
    except Exception as e:
        return False, f"derleme istisnasi: {e}", src
    try:
        cpu = CPU(words).run(max_cycles=20_000_000)
    except Exception as e:
        return False, f"CPU istisnasi: {e}", src
    try:
        ref = Kirm(parse(src))
        ref.kos()
    except Exception as e:
        return False, f"yorumlayici istisnasi: {e}", src
    if cpu.log != ref.log:
        return False, f"LOG SAPMASI:\nCPU={cpu.log[:12]}\nREF={ref.log[:12]}", src
    return True, "ok", src


def main():
    adet = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    rng = random.Random(20260921)
    basarisiz = 0
    for i in range(adet):
        ok, mesaj, src = bir_test(i, rng)
        if not ok:
            basarisiz += 1
            print(f"--- FAIL #{i}: {mesaj}")
            with open(f"fuzz_fail_{i}.cin", "w") as f:
                f.write(src)
    print(f"fuzz: {adet - basarisiz}/{adet} gecti")
    sys.exit(1 if basarisiz else 0)


if __name__ == "__main__":
    main()
