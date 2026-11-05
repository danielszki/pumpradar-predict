#!/usr/bin/env python3
"""Gera o ícone PNG do PumpRadar usando apenas a stdlib (sem PIL)."""
import struct
import sys
import zlib


def png_bytes(w, h, rgba_rows):
    def chunk(tag, data):
        block = tag + data
        return struct.pack(">I", len(data)) + block + struct.pack(">I", zlib.crc32(block) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in row) for row in rgba_rows)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def inside_rounded(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def make_icon(out_path, size=256):
    c_hi = (249, 115, 22)   # laranja
    c_lo = (239, 68, 68)    # vermelho
    c_bg_a = (12, 8, 18)
    c_bg_b = (48, 18, 24)
    white = (255, 244, 235)
    green = (52, 211, 153)

    x0, y0, x1, y1 = size * 0.16, size * 0.20, size * 0.84, size * 0.80
    rad = size * 0.10
    cx, cy = size * 0.5, size * 0.50

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            t = (x / size + y / size) / 2
            c = lerp(c_bg_a, c_bg_b, t)
            a = 255

            if inside_rounded(x, y, x0, y0, x1, y1, rad):
                c = lerp(c_lo, c_hi, (x / (2 * size)) + (y / (2 * size)))

            # aneis de radar (meio)
            for rr in (17, 27, 37):
                d = abs(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 - rr * (size / 256))
                if d <= 1.1:
                    c = white if rr < 30 else (255, 200, 150)

            # alvo central (tick verde p/ cima)
            ax, ay = size * 0.50, size * 0.40
            if y >= int(ay) and y <= int(size * 0.60):
                fx = (y - ay) / (size * 0.20)
                half = fx * (size * 0.10)
                if abs(x - ax) <= half:
                    c = white
            if size * 0.475 <= x <= size * 0.525 and size * 0.60 <= y <= size * 0.70:
                c = white
            # ponto de colisao/volta (alvo vermelho-claro)
            if dcheck := abs(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 - size * 0.115) < 2.2:
                c = white

            row.append((c[0], c[1], c[2], a))
        rows.append(row)

    with open(out_path, "wb") as f:
        f.write(png_bytes(size, size, rows))
    print("ícone escrito em", out_path)


if __name__ == "__main__":
    make_icon(sys.argv[1] if len(sys.argv) > 1 else "pumpradar.png")