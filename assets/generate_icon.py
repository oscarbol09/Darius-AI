"""
generate_icon.py — Generador de Iconos de Alta Resolución para DARIUS AI
========================================================================
Crea un icono .ico multi-resolución (256, 128, 64, 48, 32, 16 px) con
la identidad visual de Darius AI (estilo Slate/Cyan, ondas sonoras y glifo 'D').
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def generate_darius_icon(output_dir: Path | None = None):
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Fondo circular con borde y sombra suave
    margin = 8
    # Outer circle (Borde Slate)
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(17, 24, 39, 255),  # #111827
        outline=(56, 189, 248, 220),  # #38BDF8
        width=6,
    )

    # 2. Anillo interior de ondas de audio
    inner_margin = 32
    draw.ellipse(
        [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
        outline=(2, 132, 199, 140),  # #0284C7
        width=3,
    )

    # 3. Ondas laterales dinámicas (arcos de audio)
    draw.arc([16, 16, size - 16, size - 16], start=140, end=220, fill=(56, 189, 248, 255), width=5)
    draw.arc([16, 16, size - 16, size - 16], start=-40, end=40, fill=(56, 189, 248, 255), width=5)

    draw.arc([46, 46, size - 46, size - 46], start=130, end=230, fill=(14, 165, 233, 200), width=4)
    draw.arc([46, 46, size - 46, size - 46], start=-50, end=50, fill=(14, 165, 233, 200), width=4)

    # 4. Glifo Central "D" estilizado
    try:
        font = ImageFont.truetype("segoeui.ttf", 110)
    except Exception:
        font = ImageFont.load_default()

    # Dibuja la 'D' en el centro
    text = "D"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - 10

    # Resplandor cian suave detrás del texto
    for offset_x in [-2, 0, 2]:
        for offset_y in [-2, 0, 2]:
            draw.text((x + offset_x, y + offset_y), text, font=font, fill=(2, 132, 199, 120))

    # Texto principal brillante
    draw.text((x, y), text, font=font, fill=(56, 189, 248, 255))

    # Punto central de energía en la base de la 'D'
    dot_r = 5
    dot_cx = size // 2
    dot_cy = size - 42
    draw.ellipse(
        [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
        fill=(52, 211, 153, 255),  # #34D399 (Verde Esmeralda)
    )

    # Guardar PNG de alta resolución
    png_path = output_dir / "darius.png"
    img.save(png_path, "PNG")

    # Guardar ICO con múltiples tamaños (256, 128, 64, 48, 32, 16)
    ico_path = output_dir / "darius.ico"
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=icon_sizes)
    print(f"[OK] Icono generado exitosamente en:\n  - {ico_path}\n  - {png_path}")
    return ico_path


if __name__ == "__main__":
    generate_darius_icon()
