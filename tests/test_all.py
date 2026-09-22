#!/usr/bin/env python3
"""silicon-cinema dogrulama kapsulu:
   1. CPU/assembler smoke testleri (elle yazilmis asm)
   2. Sabit programlarda diferansiyel kapisi (derleyici+CPU == yorumlayici)
   3. Demo programlarinin kisa kosullarinda diferansiyel kare eslesmesi
   4. Fuzzer (rastgele programlar)

Kos: python3 tests/test_all.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cin.cin_lang import derle, parse
from cin.isa import CPU, FB_W, xorshift
from cin.interp import Kirm

GECTI = 0


def kontrol(ad, kosul, detay=""):
    global GECTI
    if kosul:
        GECTI += 1
        print(f"  [ok] {ad}")
    else:
        print(f"  [FAIL] {ad} {detay}")
        sys.exit(1)


# ---------------------------------------------------------------- 1. smoke
print("1) CPU + assembler smoke")
w, _ = derle("fn main() { let a = 5; log(a); }")
assert CPU(w).run().log == [5]
kontrol("let + log", True)

src = """
fn fib(n) {
  if (n < 2) { return n; }
  return fib(n - 1) + fib(n - 2);
}
fn main() { log(fib(15)); }
"""
cpu = CPU(derle(src)[0]).run()
kontrol("recursion fib(15)=610", cpu.log == [610], cpu.log)

# ---------------------------------------------------------------- 2. demos differential
print("2) demo programlari: derlenmis CPU == yorumlayici (kisa kosu)")
for prog, frames in [("starfield", 8), ("life", 2), ("mandel", 1),
                     ("xorfire", 4), ("balls", 15)]:
    src = open(f"programs/{prog}.cin", encoding="utf-8").read()
    src = src.replace("$SEED", "77").replace("$FRAMES", str(frames))
    words, _ = derle(src)
    cpu = CPU(words).run(max_cycles=400_000_000)
    ref = Kirm(parse(src))
    ref.kos()
    ref_duz = [[p for row in rf for p in row] for rf in ref.frames]
    kontrol(f"{prog}: {frames} kare birebir",
            len(cpu.frames) == len(ref_duz) and
            all(cf == rf for cf, rf in zip(cpu.frames, ref_duz)),
            f"kare sayisi {len(cpu.frames)} vs {len(ref_duz)}")

# ---------------------------------------------------------------- 3. fuzzer
print("3) fuzzer (60 rastgele program)")
import random
import fuzz
rng = random.Random(20260921)
kotu = 0
for i in range(60):
    ok, mesaj, src = fuzz.bir_test(i, rng)
    if not ok:
        kotu += 1
        print(f"  [FAIL] #{i}: {mesaj}")
kontrol("fuzz 60/60", kotu == 0, f"{kotu} hata")

print(f"\nTUM KAPILAR GECTI ({GECTI} kontrol)")
