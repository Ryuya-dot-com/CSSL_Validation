#!/usr/bin/env python3
"""Generate controlled abstract object SVG files for the validation task."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "images" / "objects"
OBJECT_IDS = list(range(1, 41))
PRACTICE_IDS = list(range(901, 906))

PALETTES = [
    ("#0f766e", "#f59e0b", "#e6fffb"),
    ("#2563eb", "#ef6c35", "#eef5ff"),
    ("#7c3aed", "#16a34a", "#f4edff"),
    ("#be123c", "#0891b2", "#fff1f3"),
    ("#6b4f2a", "#2f855a", "#fff7e6"),
    ("#0f4c81", "#d97706", "#edf7ff"),
    ("#8a3ffc", "#d9480f", "#f7f0ff"),
    ("#006d77", "#9b2226", "#e9fbf8"),
]


def visual_family(object_id: int) -> int:
    variant = (object_id - 1) // 8
    return ((object_id - 1) + variant * 3) % 8


def image_name(object_id: int) -> str:
    if object_id >= 900:
        return f"practice_{object_id}.svg"
    return f"object_{object_id:03d}.svg"


def render_svg(object_id: int) -> str:
    variant = (object_id - 1) // 8
    main, accent, pale = PALETTES[((object_id - 1) * 3 + variant) % len(PALETTES)]
    shape = visual_family(object_id)
    rotate = ((object_id * 17) % 34) - 17
    dot_shift = (variant % 4) * 8
    stroke_width = 7 + (variant % 3)

    if shape == 0:
        body = (
            f'<path d="M100 28 L156 61 L146 134 L100 171 L54 134 L44 61 Z" '
            f'fill="{pale}" stroke="{main}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
    elif shape == 1:
        body = (
            f'<rect x="45" y="43" width="110" height="110" rx="{24 + variant * 2}" '
            f'fill="{pale}" stroke="{main}" stroke-width="{stroke_width}"/>'
        )
    elif shape == 2:
        body = (
            f'<path d="M100 32 C136 32 162 58 162 93 C162 134 130 164 90 164 '
            f'C58 164 38 143 38 111 C38 66 60 32 100 32 Z" fill="{pale}" '
            f'stroke="{main}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
    elif shape == 3:
        body = (
            f'<path d="M56 54 C88 26 132 30 152 62 C174 98 146 154 102 166 '
            f'C61 177 30 143 42 98 C47 80 44 66 56 54 Z" fill="{pale}" '
            f'stroke="{main}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
    elif shape == 4:
        body = (
            f'<path d="M100 26 L118 72 L166 76 L128 106 L141 154 L100 128 '
            f'L59 154 L72 106 L34 76 L82 72 Z" fill="{pale}" stroke="{main}" '
            f'stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
    elif shape == 5:
        body = (
            f'<path d="M48 83 C48 55 69 38 100 38 C131 38 152 55 152 83 '
            f'L152 127 C152 148 131 164 100 164 C69 164 48 148 48 127 Z" '
            f'fill="{pale}" stroke="{main}" stroke-width="{stroke_width}"/>'
        )
    elif shape == 6:
        body = (
            f'<path d="M100 31 L159 96 L126 164 L74 164 L41 96 Z" fill="{pale}" '
            f'stroke="{main}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
    else:
        body = (
            f'<path d="M42 101 C42 62 62 42 101 42 C140 42 158 62 158 101 '
            f'C158 140 140 158 101 158 C62 158 42 140 42 101 Z M74 101 '
            f'C74 119 84 128 101 128 C118 128 126 119 126 101 C126 84 118 74 '
            f'101 74 C84 74 74 84 74 101 Z" fill="{pale}" stroke="{main}" '
            f'stroke-width="{stroke_width}" fill-rule="evenodd"/>'
        )

    decorations = (
        f'<circle cx="{66 + dot_shift}" cy="70" r="{9 + (variant % 2) * 3}" '
        f'fill="{accent}" opacity="0.92"/>'
        f'<circle cx="{132 - dot_shift / 2}" cy="124" r="{7 + (variant % 3)}" '
        f'fill="{accent}" opacity="0.78"/>'
        f'<path d="M64 148 C86 {132 - dot_shift}, 114 {166 - dot_shift}, 138 142" '
        f'fill="none" stroke="{accent}" stroke-width="7" stroke-linecap="round" opacity="0.82"/>'
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" role="img">
  <ellipse cx="100" cy="178" rx="55" ry="11" fill="#17201d" opacity="0.12"/>
  <g transform="rotate({rotate} 100 100)">
    {body}
    {decorations}
  </g>
</svg>
'''


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for object_id in OBJECT_IDS + PRACTICE_IDS:
        (OUT_DIR / image_name(object_id)).write_text(render_svg(object_id), encoding="utf-8")
    print(f"Wrote {len(OBJECT_IDS) + len(PRACTICE_IDS)} SVG files to {OUT_DIR}")


if __name__ == "__main__":
    main()
