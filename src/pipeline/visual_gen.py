"""Visual generation: Pillow text slides + matplotlib chart."""
import asyncio
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from src.logger import get_formatted_logger

logger = get_formatted_logger("visual_gen")

W, H = 1280, 720
BG = (18, 24, 38)
FG = (240, 240, 240)
ACCENT = (80, 180, 255)
MARGIN = 80


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _title_slide(title: str) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    font = _font(64)
    lines = _wrap(draw, title, font, W - 2 * MARGIN)
    y = H // 2 - len(lines) * 40
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=ACCENT)
        y += 80
    draw.text((MARGIN, H - 60), "Chemistry Learner", font=_font(24), fill=FG)
    return img


def _section_slide(heading: str, key_points: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.text((MARGIN, 60), heading, font=_font(44), fill=ACCENT)

    y = 200
    for point in key_points:
        bullet_font = _font(32)
        draw.ellipse((MARGIN, y + 12, MARGIN + 14, y + 26), fill=ACCENT)
        for line in _wrap(draw, str(point), bullet_font, W - 2 * MARGIN - 40):
            draw.text((MARGIN + 40, y), line, font=bullet_font, fill=FG)
            y += 46
        y += 24
    return img


def _chart(query: str) -> Optional[Image.Image]:
    """1 matplotlib chart: pH scale hoặc bonding đơn giản."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ql = query.lower()
    fig = None
    try:
        if "ph scale" in ql or "ph" in ql.split():
            fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
            gradient = [(i / 14, color, 1 - i / 14) for i, color in
                        zip(range(15), ["red"] * 15)]
            import matplotlib.colors as mcolors

            cmap = mcolors.LinearSegmentedColormap.from_list(
                "ph", ["#d62728", "#ff9896", "#c7c7c7", "#9edae6", "#1f77b4"]
            )
            bars = ax.bar(range(0, 15), [10] * 15, color=cmap([i / 14 for i in range(15)]))
            ax.set_xticks(range(0, 15))
            ax.set_xlabel("pH value", fontsize=16)
            ax.set_yticks([])
            ax.set_title("The pH Scale (0-14)", fontsize=22)
            ax.axvline(7, color="white", linestyle="--", linewidth=2)
            ax.text(7.15, 9.3, "Neutral (7)", fontsize=13, color="white")
            ax.text(1.3, 9.3, "Acidic", fontsize=13, color="white")
            ax.text(11, 9.3, "Basic", fontsize=13, color="white")
            fig.patch.set_facecolor("#121826")
            ax.set_facecolor("#121826")
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_color("white")
        else:
            fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
            ax.set_xlim(0, 10)
            ax.set_ylim(0, 6)
            ax.set_axis_off()
            ax.set_title(
                "Ionic: transfer   vs   Covalent: share",
                fontsize=20, color="white",
            )
            fig.patch.set_facecolor("#121826")
            ax.plot(1.5, 3, "o", markersize=22, color="#d62728")
            ax.plot(3.5, 3, "o", markersize=22, color="#1f77b4")
            ax.annotate("", xy=(3.3, 3.25), xytext=(2.0, 3.25),
                        arrowprops=dict(arrowstyle="->", color="white", lw=2))
            ax.text(1.2, 2.2, "Na", color="white", fontsize=14)
            ax.text(3.3, 2.2, "Cl", color="white", fontsize=14)
            ax.text(0.4, 4.2, "Ionic", color="white", fontsize=16)
            ax.plot(6.5, 3, "o", markersize=18, color="#2ca02c")
            ax.plot(8.5, 3, "o", markersize=18, color="#2ca02c")
            ax.plot([6.5, 8.5], [3, 3], color="white", lw=2)
            ax.text(6.1, 2.2, "H", color="white", fontsize=14)
            ax.text(8.3, 2.2, "H", color="white", fontsize=14)
            ax.text(5.6, 4.2, "Covalent", color="white", fontsize=16)

        import io

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
        buf.seek(0)
        return Image.open(buf).convert("RGB")
    except Exception as exc:
        logger.error(f"Chart gen fail: {exc}")
        return None
    finally:
        if fig is not None:
            try:
                plt.close(fig)
            except Exception:
                pass


def generate_visuals_sync(query: str, script: dict, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    slides: list[tuple[str, Image.Image]] = [
        ("slide_00", _title_slide(str(script.get("title", "Lesson")))),
    ]
    for i, section in enumerate(script.get("sections", []), start=1):
        slides.append(
            (
                f"slide_{i:02d}",
                _section_slide(
                    str(section.get("heading", "")),
                    [str(p) for p in section.get("key_points", [])],
                ),
            )
        )

    chart = _chart(query)
    if chart is not None:
        slides.append(("chart", chart))

    for name, img in slides:
        path = images_dir / f"{name}.png"
        img.save(path)
        paths.append(str(path))
        logger.debug(f"Slide saved: {path.name}")

    logger.info(f"Visual gen: {len(paths)} slides")
    return paths


async def generate_visuals(query: str, script: dict, out_dir: Path) -> list[str]:
    return await asyncio.to_thread(generate_visuals_sync, query, script, out_dir)