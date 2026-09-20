"""
generate_icon.py — Generador Oficial de Activos Visuales para DARIUS AI
========================================================================
Procesa el logotipo de alta resolución y genera todos los derivados
necesarios para la aplicación de escritorio, instalador, documentación y GitHub:
  - assets/darius.ico (Multi-resolución: 256, 128, 64, 48, 32, 16 px)
  - assets/darius.png & assets/logo.png (Logotipo completo en alta resolución)
  - assets/logo_icon.png (Glifo 'D' transparente 512x512)
  - assets/logo_badge.png (Insignia Squircle de la aplicación 512x512)
  - assets/favicon.ico & assets/favicon.png (Favicons estándar para web/docs)
  - assets/social_preview.png & docs/assets/social_preview.png (Banner Open Graph 1280x640)
  - assets/banner.png & docs/assets/banner.png (Banner de cabecera 1200x420)
"""

import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def generate_all_assets(output_dir: Path | None = None) -> dict[str, Path]:
    repo_root = Path(__file__).resolve().parent.parent
    if output_dir is None:
        output_dir = repo_root / "assets"
    docs_dir = repo_root / "docs" / "assets"

    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Localizar imagen fuente
    source_candidates = [
        output_dir / "logo_source.png",
        Path(r"C:\Users\dario\OneDrive\Documentos\Repositorio_Ayuda\logo darius.png"),
        output_dir / "darius.png",
    ]

    source_path = None
    for cand in source_candidates:
        if cand.exists():
            source_path = cand
            break

    if not source_path:
        raise FileNotFoundError("No se encontró ninguna imagen fuente del logo de Darius AI.")

    # Copiar a logo_source.png como activo inmutable si no existe
    if source_path != output_dir / "logo_source.png":
        shutil.copy2(source_path, output_dir / "logo_source.png")
        source_path = output_dir / "logo_source.png"

    orig = Image.open(source_path)

    # 2. Extraer glifo 'D' con matting transparente
    glyph_crop = orig.crop((265, 385, 485, 605))
    arr_g = np.array(glyph_crop, dtype=np.float32)
    rg, gg, bg, ag = arr_g[:, :, 0], arr_g[:, :, 1], arr_g[:, :, 2], arr_g[:, :, 3]
    max_g = np.maximum(np.maximum(rg, gg), bg)

    blue_dom = np.clip((bg - np.maximum(rg, gg) - 8.0) / 20.0, 0.0, 1.0)
    bright_fac = np.clip((max_g - 20.0) / 30.0, 0.0, 1.0)
    alpha_fac = blue_dom * bright_fac
    alpha_fac = alpha_fac * alpha_fac * (3.0 - 2.0 * alpha_fac)

    new_ag = ag * alpha_fac
    clean_glyph_arr = np.dstack([rg, gg, bg, new_ag]).astype(np.uint8)
    clean_glyph = Image.fromarray(clean_glyph_arr, "RGBA")

    ys, xs = np.where(new_ag > 25)
    tight_glyph = clean_glyph.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

    # 3. Guardar logo_icon.png transparente (512x512)
    icon_size = 512
    icon_trans = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    target_h = int(icon_size * 0.85)
    scale = target_h / tight_glyph.height
    target_w = int(tight_glyph.width * scale)
    scaled_glyph = tight_glyph.resize((target_w, target_h), Image.Resampling.LANCZOS)
    icon_trans.paste(scaled_glyph, ((icon_size - target_w) // 2, (icon_size - target_h) // 2), scaled_glyph)
    icon_trans.save(output_dir / "logo_icon.png", "PNG")

    # 4. Crear Squircle App Badge (512x512)
    badge = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    draw_b = ImageDraw.Draw(badge)
    margin = 24
    radius = 96
    draw_b.rounded_rectangle(
        [margin, margin, icon_size - margin, icon_size - margin],
        radius=radius,
        fill=(15, 23, 42, 255),
        outline=(56, 189, 248, 200),
        width=6,
    )

    glow = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        [icon_size // 4, icon_size // 4, 3 * icon_size // 4, 3 * icon_size // 4],
        fill=(14, 165, 233, 50),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(35))
    badge.alpha_composite(glow)

    target_hb = int(icon_size * 0.66)
    scale_b = target_hb / tight_glyph.height
    target_wb = int(tight_glyph.width * scale_b)
    scaled_glyph_b = tight_glyph.resize((target_wb, target_hb), Image.Resampling.LANCZOS)
    badge.paste(scaled_glyph_b, ((icon_size - target_wb) // 2, (icon_size - target_hb) // 2), scaled_glyph_b)
    badge.save(output_dir / "logo_badge.png", "PNG")

    # 5. Generar darius.ico multi-resolución
    ico_path = output_dir / "darius.ico"
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    badge.save(ico_path, format="ICO", sizes=icon_sizes)

    # 6. Generar favicons
    fav_sizes = [(48, 48), (32, 32), (16, 16)]
    badge.save(output_dir / "favicon.ico", format="ICO", sizes=fav_sizes)
    fav_32 = badge.resize((32, 32), Image.Resampling.LANCZOS)
    fav_32.save(output_dir / "favicon.png", "PNG")
    fav_32.save(docs_dir / "favicon.png", "PNG")

    # 7. Generar Logotipo Completo Transparente
    raw_lockup = orig.crop((260, 380, 1300, 610))
    arr_l = np.array(raw_lockup, dtype=np.float32)
    rl, gl, bl, al = arr_l[:, :, 0], arr_l[:, :, 1], arr_l[:, :, 2], arr_l[:, :, 3]
    max_l = np.maximum(np.maximum(rl, gl), bl)
    alpha_factor_l = np.clip((max_l - 20.0) / 45.0, 0.0, 1.0)
    alpha_factor_l = alpha_factor_l * alpha_factor_l * (3.0 - 2.0 * alpha_factor_l)
    new_al = al * alpha_factor_l
    clean_lockup = Image.fromarray(np.dstack([rl, gl, bl, new_al]).astype(np.uint8), "RGBA")
    clean_lockup.save(output_dir / "logo.png", "PNG")
    clean_lockup.save(output_dir / "darius.png", "PNG")

    # 8. Generar Social Preview (1280x640)
    w, h = 1280, 640
    left = (orig.width - w) // 2
    top = (orig.height - h) // 2
    crop_center = orig.crop((left, top, left + w, top + h))

    social_img = Image.new("RGBA", (w, h), (11, 15, 25, 255))
    social_img.paste(crop_center, (0, 0), crop_center)

    draw_s = ImageDraw.Draw(social_img)
    try:
        font_tag = ImageFont.truetype("segoeui.ttf", 16)
        font_bold = ImageFont.truetype("segoeuib.ttf", 15)
    except Exception:
        font_tag = ImageFont.load_default()
        font_bold = font_tag

    badges = [
        ("WIN32 NATIVE", (56, 189, 248)),
        ("MULTI-LLM BYOK", (168, 85, 247)),
        ("NEURAL TTS 24kHz", (236, 72, 153)),
        ("OBSIDIAN BRAIN", (147, 51, 234)),
        ("COMPUTER USE", (34, 197, 94)),
        ("60 FPS CANVAS", (245, 158, 11)),
    ]

    total_bw = 0
    badge_pads = []
    for text, color in badges:
        bbox = draw_s.textbbox((0, 0), text, font=font_bold)
        bw = bbox[2] - bbox[0] + 28
        badge_pads.append((text, color, bw, 32))
        total_bw += bw + 10
    total_bw -= 10

    start_x = (w - total_bw) // 2
    by = 485

    for text, color, bw, bh in badge_pads:
        draw_s.rounded_rectangle(
            [start_x, by, start_x + bw, by + bh],
            radius=16,
            fill=(15, 23, 42, 220),
            outline=(*color, 160),
            width=1,
        )
        bbox = draw_s.textbbox((0, 0), text, font=font_bold)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw_s.text(
            (start_x + (bw - tw) // 2, by + (bh - th) // 2 - 1),
            text,
            font=font_bold,
            fill=(241, 245, 249, 255),
        )
        start_x += bw + 10

    footer = "oscarbol09/Darius-AI · Asistente de Escritorio Autónomo para Windows · C++ Standalone"
    bbox_f = draw_s.textbbox((0, 0), footer, font=font_tag)
    tw_f = bbox_f[2] - bbox_f[0]
    draw_s.text(((w - tw_f) // 2, 580), footer, font=font_tag, fill=(100, 116, 139, 220))

    social_img.save(output_dir / "social_preview.png", "PNG")
    social_img.save(docs_dir / "social_preview.png", "PNG")

    # 9. Generar Banner de Cabecera (1200x420)
    banner_w, banner_h = 1200, 420
    banner = Image.new("RGBA", (banner_w, banner_h), (11, 15, 25, 255))
    crop_b = orig.crop(
        (
            (orig.width - banner_w) // 2,
            (orig.height - banner_h) // 2,
            (orig.width + banner_w) // 2,
            (orig.height + banner_h) // 2,
        )
    )
    banner.paste(crop_b, (0, 0), crop_b)
    banner.save(output_dir / "banner.png", "PNG")
    banner.save(docs_dir / "banner.png", "PNG")

    return {
        "ico": ico_path,
        "badge": output_dir / "logo_badge.png",
        "icon": output_dir / "logo_icon.png",
        "logo": output_dir / "logo.png",
        "social": output_dir / "social_preview.png",
        "banner": output_dir / "banner.png",
    }


if __name__ == "__main__":
    generated = generate_all_assets()
    print("[OK] Todos los activos visuales de Darius AI generados exitosamente:")
    for k, v in generated.items():
        print(f"  - {k}: {v}")
