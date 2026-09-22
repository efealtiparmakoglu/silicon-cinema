#!/usr/bin/env python3
"""silicon-cinema render: CIN programini derle, CPU'da kostur, kareleri GIF yap."""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cin.cin_lang import derle
from cin.isa import CPU, FB_H, FB_W


def png_yaz(path, img):
    h, w, _ = img.shape
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += img[y].tobytes()

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def rgb565_kare(frame):
    img = []
    for y in range(FB_H):
        px = bytearray()
        for c in frame[y * FB_W:(y + 1) * FB_W]:
            r = (c >> 11) & 31
            g = (c >> 5) & 63
            b = c & 31
            px += bytes((r * 255 // 31, g * 255 // 63, b * 255 // 31))
        img.append(px)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    sc = json.load(open(args.scene, encoding="utf-8"))
    src = open(f"programs/{sc['program']}.cin", encoding="utf-8").read()
    frames_n = sc.get("frames", 240)
    src = src.replace("$SEED", str(sc.get("seed", 1))).replace("$FRAMES", str(frames_n))

    words, labels = derle(src)
    cpu = CPU(words).run(max_cycles=sc.get("max_cycles", 2_000_000_000))
    print(f"  derlendi: {len(words)} sozcuk, {cpu.cycles:,} cycle, "
          f"{len(cpu.frames)} kare, {len(labels)} etiket")

    out = sc["output"]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = out + ".frames"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)

    for i, fr in enumerate(cpu.frames):
        img = rgb565_kare(fr)
        # PNG'yi satirlardan kur
        h, w = FB_H, FB_W
        raw = bytearray()
        for y in range(h):
            raw.append(0)
            raw += img[y]

        def chunk(tag, data):
            return (struct.pack(">I", len(data)) + tag + data
                    + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        with open(f"{tmp}/f{i:05d}.png", "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                    + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))

    # son kareyi PNG olarak birak
    shutil.copy(f"{tmp}/f{len(cpu.frames) - 1:05d}.png", out.replace(".gif", ".png"))

    fps = sc.get("fps", 20)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", f"{tmp}/f%05d.png",
                    "-vf", "palettegen=max_colors=256:stats_mode=diff", f"{tmp}/pal.png"],
                   check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", f"{tmp}/f%05d.png", "-i", f"{tmp}/pal.png",
                    "-lavfi", "paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
                    "-loop", "0", out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"== BİTTİ -> {out}")


if __name__ == "__main__":
    main()
