"""Render a text file (an excerpt of a real run log) as a terminal-style PNG.
The image is a readable copy of the log text, not a photo of a screen; the excerpt file is kept beside it.
Usage: python make_screenshot.py <input.txt> <output.png> "<title>" [max_lines] [max_chars]
max_chars (default 118) is the line width before wrapping; the image widens to fit it.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 15
PAD = 24
LINE_H = 20
BG = (30, 30, 34)
TITLEBAR = (45, 45, 50)
FG = (223, 223, 225)
GREEN = (98, 209, 150)
RED = (235, 100, 100)
YELLOW = (230, 190, 90)
CYAN = (110, 190, 230)

def color_for(line):
    l = line.strip()
    if any(k in l for k in ["PASS", "SUCCESS", "COMPLETED", "OK ", "✓"]) or l.startswith("OK"):
        return GREEN
    if any(k in l for k in ["FAIL", "ERROR", "FAILED"]):
        return RED
    if any(k in l for k in ["WARN", "429", "500", "RUNNING", "killed", "Killed"]):
        return YELLOW
    if l.startswith("===") or l.startswith("$") or l.startswith("#"):
        return CYAN
    return FG

def wrap(line, max_chars=118):
    if len(line) <= max_chars:
        return [line]
    out = []
    while len(line) > max_chars:
        out.append(line[:max_chars])
        line = "  " + line[max_chars:]
    out.append(line)
    return out

def main():
    infile, outfile, title = sys.argv[1], sys.argv[2], sys.argv[3]
    max_lines = int(sys.argv[4]) if len(sys.argv) > 4 else 60
    max_chars = int(sys.argv[5]) if len(sys.argv) > 5 else 118
    with open(infile) as f:
        raw_lines = [l.rstrip("\n").expandtabs(14) for l in f.readlines()]
    lines = []
    for l in raw_lines:
        lines.extend(wrap(l, max_chars))
    lines = lines[:max_lines]

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bold_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 13)

    width = max(1400, int(PAD * 2 + max_chars * 9.1))
    height = PAD * 2 + 36 + len(lines) * LINE_H
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, width, 36], fill=TITLEBAR)
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (97, 197, 84)]):
        draw.ellipse([16 + i * 22, 12, 28 + i * 22, 24], fill=c)
    draw.text((width / 2 - len(title) * 3.6, 10), title, font=bold_font, fill=(210, 210, 214))

    y = 36 + PAD
    for line in lines:
        draw.text((PAD, y), line, font=font, fill=color_for(line))
        y += LINE_H

    img.save(outfile)
    print(f"wrote {outfile} ({width}x{height}, {len(lines)} lines)")

if __name__ == "__main__":
    main()
