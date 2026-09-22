# 🖥️ silicon-cinema

**EN:** A complete computing stack, built from scratch and verified end-to-end: a JSON-configurable **32-bit CPU emulator**, an **assembler**, a **compiler for a home-made systems language (CIN)**, and a framebuffer "OS" — then **demo programs written in CIN**, compiled, executed on the emulated CPU, and filmed as animated GIFs.

**TR:** Sıfırdan inşa edilmiş ve uçtan uca doğrulanmış eksiksiz bir bilgisayar yığını: **32-bit CPU emülatörü**, **assembler**, **kendi yazdığımız CIN dilinin derleyicisi** ve framebuffer "işletim sistemi" — sonra CIN ile yazılmış **demo programları**: derlenir, taklit CPU'da çalışır, animasyonlu GIF olarak filmlenir.

![starfield](renders/starfield.gif)

> Bu GIF'teki her piksel, **kendi derleyicimizle derlenen kendi dilimizle yazılmış** programın, **kendi yazdığımız CPU'da** çalışmasından çıktı. Hiçbir kütüphane, hiçbir hazır emülatör yok.

## 🖼️ Gallery / Galeri

### ✨ Starfield / Yıldız Alanı — [`programs/starfield.cin`](programs/starfield.cin)
![starfield](renders/starfield.gif)
3D perspective starfield with depth-based color, running at ~1M instructions per second on the emulated CPU. — *Derinliğe göre renklenen 3B yıldız alanı.*

### 🦠 Life / Yaşam — [`programs/life.cin`](programs/life.cin)
![life](renders/life.gif)
Conway's Game of Life on a 128×72 torus — 9,216 cells updated per frame, in CIN. — *128×72 torusta Conway'in Yaşam Oyunu — kare başına 9.216 hücre.*

### 🌀 XOR Fire / Ateş Tüneli — [`programs/xorfire.cin`](programs/xorfire.cin)
![xorfire](renders/xorfire.gif)
The classic demoscene XOR texture, scrolling through a fire palette. — *Klasik demoscene XOR dokusu, ateş paletinde akıyor.*

### ⚛️ Mandelbrot — [`programs/mandel.cin`](programs/mandel.cin)
![mandel](renders/mandel.gif)
Fractals in **fixed-point 8.8 arithmetic** — the language has no floats, so we don't need them. — *Sabit noktalı 8.8 aritmetikle fraktallar — dilde kayan nokta yok, gerek de yok.*

### 🔴 Balls / Toplar — [`programs/balls.cin`](programs/balls.cin)
![balls](renders/balls.gif)
Bouncing particles with wrap-around physics and per-particle colors. — *Sekerek oynayan, renkli parçacıklar.*

## 🧱 The stack / Yığın

```
programs/*.cin  →  cin/cin_lang.py (lexer→parser→codegen)  →  CIN-32 assembly
                →  cin/assembler.py                        →  makine sözcükleri
                →  cin/isa.py (CPU emülatörü)              →  framebuffer
                →  render.py                               →  GIF
      (paralelde) cin/interp.py — referans yorumlayıcı: her adım diferansiyel test edilir
```

| Katman | Detay |
|---|---|
| 🧮 ISA (CIN-32) | 32-bit word-addressed, 24 instructions, fixed 2-word encoding, 6 general regs + sp + ra |
| 🖥️ CPU | Fetch-decode-execute, 64K-word memory map: code / globals / stack / framebuffer (128×72 RGB565) / heap |
| 🔧 Assembler | Two-pass, labels, relative branches, absolute LDI |
| 🌐 CIN language | int32 wrap semantics, arrays, if/else, while, recursive functions, 6 builtins |
| ⚙️ Compiler | Recursive-descent parser → stack-machine codegen, frame pointers, caller/callee convention |
| 🔍 Verifier | **Differential testing** (compiled+CPU vs tree-walking interpreter, frame-exact) + **fuzzer** (150+ random programs) |

## ✅ Verification / Doğrulama — projenin kalbi

**EN:** A compiler without a proof is just a guess. Every layer is checked against an independent implementation: the CIN program is executed **both** by the tree-walking interpreter **and** by the compiled-code-on-emulated-CPU path, and the framebuffer frames must match **exactly**. The fuzzer then generates hundreds of random programs to hunt for semantic drift. Bugs this gate caught during development: unsigned/pop sign-conversion, double-push call convention, stack-leaking loop back-edges (added a real `JMP`), local slot clobbering.

**TR:** Kanıtsız derleyici tahmindir. Her katman bağımsız bir gerçeklemeye karşı denetlenir: CIN programı hem ağaç-gezgin yorumlayıcıda hem derlenip taklit CPU'da çalıştırılır; framebuffer kareleri **tek pikseline kadar** eşleşmek zorundadır. Fuzzer yüzlerce rastgele programla semantik kaymasını avlar. Bu kapı geliştirme sırasında şunları yakaladı: işaretsiz POP dönüşümü, çift-push çağrı sözleşmesi, döngü kenarlarında yığın sızıntısı (gerçek `JMP` eklendi), yerel yuva ezilmesi.

```bash
python3 tests/test_all.py   # tüm kapılar
python3 fuzz.py 300         # 300 rastgele program
```

## 🚀 Usage / Kullanım

```bash
pip install numpy   # yalnızca referans yorumlayıcı doğrulaması için gerekmiyor; CPU saf Python
python3 render.py --scene scenes/starfield.json
python3 render.py --scene scenes/life.json --preview
```

GIF birleştirme için ffmpeg. Gerisi yalnızca stdlib.

## 🎛️ ISA quick reference / ISA kısaca

```asm
ldi x1, 100      ; 16-bit yükle        add x1, x2, x3
ld  x1, x2, x3   ; x1 = mem[x2+x3]     sub mul div mod xor or and shl shr slt
st  x1, x2, x3   ; mem[x1+x2] = x3     beq/bne/blt x1, etiket   ; x0 ile karşılaştırır
push x1 / pop x1 jal f / jr            ; jal ra'yı yığına iter
syscall 1..6     ; pixel, flush, rand, log, alloc, getpixel
```

Sahne JSON'u: program, seed, kare sayısı, fps, çıktı yolu. Seed değiştir → aynı program, bambaşka evren.

## 🧪 Why / Neden

**TR:** İnsanlar emülatör KULLANIR; bu proje emülatörün, derleyicinin, dilin ve doğrulamanın tamamını İNŞA EDER — ve "çalışıyor" demek yerine çalıştığını **kanıtlar**: iki bağımsız gerçekleme, tek piksel hassasiyetinde eşleşme, yüzlerce rastgele program. Blender reposu hazır render motorunu, bu repo ise bir bilgisayarın beynini sıfırdan döktü.

## 📄 License

MIT
