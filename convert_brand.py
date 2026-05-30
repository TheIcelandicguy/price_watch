"""Convert the brand SVGs to PNGs using resvg_py.

resvg is a Rust-based SVG renderer with no system library dependencies,
faster and more reliable than headless Chrome for static SVG-to-PNG.

Usage: python convert_brand.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import resvg_py

BRAND_DIR = Path(__file__).parent / "custom_components" / "price_watch" / "brand"


def render(svg_path: Path, out_path: Path, width: int, height: int) -> None:
    """Render an SVG file to a PNG at the given dimensions."""
    svg_text = svg_path.read_text(encoding="utf-8")
    png_bytes = resvg_py.svg_to_bytes(
        svg_string=svg_text,
        width=width,
        height=height,
    )
    out_path.write_bytes(bytes(png_bytes))
    print(f"  Wrote {out_path.name} ({out_path.stat().st_size:,} bytes)")


def main() -> None:
    if not BRAND_DIR.exists():
        print(f"ERROR: brand dir missing: {BRAND_DIR}", file=sys.stderr)
        sys.exit(1)

    # Light variants
    print("Rendering icon.png (256x256)...")
    render(BRAND_DIR / "icon.svg", BRAND_DIR / "icon.png", 256, 256)
    print("Rendering icon@2x.png (512x512)...")
    render(BRAND_DIR / "icon.svg", BRAND_DIR / "icon@2x.png", 512, 512)
    print("Rendering logo.png (256x256)...")
    render(BRAND_DIR / "logo.svg", BRAND_DIR / "logo.png", 256, 256)
    print("Rendering logo@2x.png (512x512)...")
    render(BRAND_DIR / "logo.svg", BRAND_DIR / "logo@2x.png", 512, 512)

    # Dark variants
    print("Rendering dark_icon.png (256x256)...")
    render(BRAND_DIR / "dark_icon.svg", BRAND_DIR / "dark_icon.png", 256, 256)
    print("Rendering dark_icon@2x.png (512x512)...")
    render(BRAND_DIR / "dark_icon.svg", BRAND_DIR / "dark_icon@2x.png", 512, 512)
    print("Rendering dark_logo.png (256x256)...")
    render(BRAND_DIR / "dark_logo.svg", BRAND_DIR / "dark_logo.png", 256, 256)
    print("Rendering dark_logo@2x.png (512x512)...")
    render(BRAND_DIR / "dark_logo.svg", BRAND_DIR / "dark_logo@2x.png", 512, 512)

    print("\nDone. Files in:", BRAND_DIR)


if __name__ == "__main__":
    main()
