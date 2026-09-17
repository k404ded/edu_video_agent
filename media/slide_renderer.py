"""
Slide Renderer: Generates 1920x1080 Full HD slide frames matching the educational presentation.

Uses Pillow to render crisp PPT-style slides:
- 16:9 widescreen (1920x1080)
- Clean card-based typography and hierarchy
- Formatted bullets and key term tags
- Title slide + section slides matching the presentation structure
"""
import os
import textwrap
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

from config import VIDEO_WIDTH, VIDEO_HEIGHT
from models.schema import PipelineResult, SlideOutput, DocumentSummary


# Color definitions (RGB)
BG_COLOR = (248, 250, 252)          # Slate 50
CARD_BG = (255, 255, 255)           # White
CARD_BORDER = (226, 232, 240)       # Slate 200
TOP_BAR_COLOR = (37, 99, 235)       # Blue 600
TEXT_PRIMARY = (15, 23, 42)         # Slate 900
TEXT_SECONDARY = (71, 85, 105)      # Slate 600
TEXT_MUTED = (148, 163, 184)        # Slate 400
ACCENT_BLUE = (37, 99, 235)         # Blue 600
TAG_BG_BLUE = (239, 246, 255)       # Blue 50
TAG_TEXT_BLUE = (29, 78, 216)       # Blue 700
TAG_BG_AMBER = (254, 243, 199)      # Amber 100
TAG_TEXT_AMBER = (180, 83, 9)       # Amber 700


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Tries to load Segoe UI or Arial from Windows fonts; falls back to default."""
    candidates = [
        ("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        ("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        ("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_rounded_card(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    radius: int = 16,
    fill=CARD_BG,
    outline=CARD_BORDER,
    width: int = 2,
):
    """Draws a rounded rectangle card."""
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wraps text so it fits within max_width pixels."""
    words = text.split()
    if not words:
        return []

    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        # Measure text width
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))
    return lines


def render_title_slide(
    doc_summary: DocumentSummary,
    output_path: str,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> str:
    """Renders the introductory title slide image (1920x1080)."""
    img = Image.new("RGB", (width, height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([0, 0, width, 16], fill=TOP_BAR_COLOR)

    # Main Center Card
    card_margin_x = 180
    card_margin_y = 150
    _draw_rounded_card(
        draw,
        (card_margin_x, card_margin_y, width - card_margin_x, height - card_margin_y),
        radius=20,
    )

    # Badge: Topic Category
    f_badge = _get_font(20, bold=True)
    draw.text((card_margin_x + 60, card_margin_y + 60), "EDUCATIONAL PRESENTATION", fill=ACCENT_BLUE, font=f_badge)

    # Main Title
    f_title = _get_font(52, bold=True)
    title_text = doc_summary.main_topic or "Educational Overview"
    title_lines = _wrap_text(title_text, f_title, width - (card_margin_x * 2) - 120, draw)
    curr_y = card_margin_y + 110
    for line in title_lines[:2]:
        draw.text((card_margin_x + 60, curr_y), line, fill=TEXT_PRIMARY, font=f_title)
        curr_y += 68

    # Divider line
    curr_y += 10
    draw.line(
        [(card_margin_x + 60, curr_y), (width - card_margin_x - 60, curr_y)],
        fill=CARD_BORDER,
        width=2,
    )
    curr_y += 30

    # Learning Objective
    f_obj_lbl = _get_font(22, bold=True)
    draw.text((card_margin_x + 60, curr_y), "🎯 Learning Objective:", fill=TEXT_SECONDARY, font=f_obj_lbl)
    curr_y += 38

    f_obj = _get_font(26, bold=False)
    obj_lines = _wrap_text(doc_summary.learning_objective or "Master key concepts.", f_obj, width - (card_margin_x * 2) - 120, draw)
    for line in obj_lines[:3]:
        draw.text((card_margin_x + 60, curr_y), line, fill=TEXT_PRIMARY, font=f_obj)
        curr_y += 40

    # Footer inside card: Audience Level
    if doc_summary.audience_level:
        f_aud = _get_font(20, bold=False)
        draw.text(
            (card_margin_x + 60, height - card_margin_y - 65),
            f"Target Audience: {doc_summary.audience_level}",
            fill=TEXT_SECONDARY,
            font=f_aud,
        )

    img.save(output_path, quality=95)
    return output_path


def render_section_slide(
    slide_out: SlideOutput,
    section_index: int,
    total_sections: int,
    output_path: str,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> str:
    """Renders a section slide image (1920x1080) with title, bullet points, tags, and cues."""
    img = Image.new("RGB", (width, height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([0, 0, width, 14], fill=TOP_BAR_COLOR)

    # Header: Counter and Section Title
    f_counter = _get_font(18, bold=True)
    draw.text((90, 48), f"SECTION {section_index} OF {total_sections}", fill=ACCENT_BLUE, font=f_counter)

    f_title = _get_font(38, bold=True)
    draw.text((90, 80), slide_out.section_title or f"Section {section_index}", fill=TEXT_PRIMARY, font=f_title)

    # Left Container: Main Content Card (Width: 1080px, Height: 810px)
    left_x1, left_y1 = 90, 160
    left_x2, left_y2 = 1180, 970
    _draw_rounded_card(draw, (left_x1, left_y1, left_x2, left_y2), radius=16)

    f_card_hdr = _get_font(22, bold=True)
    draw.text((left_x1 + 40, left_y1 + 36), "Key Concepts & Information", fill=TEXT_SECONDARY, font=f_card_hdr)

    # Divider inside left card
    draw.line([(left_x1 + 40, left_y1 + 75), (left_x2 - 40, left_y1 + 75)], fill=CARD_BORDER, width=2)

    # Bullets
    f_bullet = _get_font(24, bold=False)
    f_bullet_icon = _get_font(22, bold=True)
    raw_lines = [l.strip("- *• \t") for l in slide_out.on_screen_content.split("\n") if l.strip()]
    if not raw_lines:
        raw_lines = [slide_out.on_screen_content]

    bullet_y = left_y1 + 105
    max_bullet_width = (left_x2 - left_x1) - 120

    for item in raw_lines:
        lines = _wrap_text(item, f_bullet, max_bullet_width, draw)
        if not lines:
            continue
        # Draw bullet dot / icon
        draw.text((left_x1 + 42, bullet_y + 2), "•", fill=ACCENT_BLUE, font=f_bullet_icon)
        for sub_line in lines:
            if bullet_y + 36 > left_y2 - 30:
                break
            draw.text((left_x1 + 75, bullet_y), sub_line, fill=TEXT_PRIMARY, font=f_bullet)
            bullet_y += 36
        bullet_y += 18  # Spacing between bullet points
        if bullet_y > left_y2 - 60:
            break

    # Right Column Top: Objective Card
    right_x1, right_y1 = 1220, 160
    right_x2, right_y2 = 1830, 480
    _draw_rounded_card(draw, (right_x1, right_y1, right_x2, right_y2), radius=16)

    f_side_hdr = _get_font(20, bold=True)
    draw.text((right_x1 + 30, right_y1 + 28), "🎯 Learning Objective", fill=ACCENT_BLUE, font=f_side_hdr)
    draw.line([(right_x1 + 30, right_y1 + 64), (right_x2 - 30, right_y1 + 64)], fill=CARD_BORDER, width=2)

    f_side_txt = _get_font(20, bold=False)
    lo_lines = _wrap_text(slide_out.learning_objective or "Understand key concepts.", f_side_txt, (right_x2 - right_x1) - 60, draw)
    lo_y = right_y1 + 84
    for line in lo_lines[:6]:
        draw.text((right_x1 + 30, lo_y), line, fill=TEXT_PRIMARY, font=f_side_txt)
        lo_y += 32

    # Right Column Bottom: Key Terms & Visual Cue Card
    r2_y1 = 510
    r2_y2 = 970
    _draw_rounded_card(draw, (right_x1, r2_y1, right_x2, r2_y2), radius=16)

    draw.text((right_x1 + 30, r2_y1 + 28), "🔑 Key Terminology", fill=TEXT_SECONDARY, font=f_side_hdr)
    draw.line([(right_x1 + 30, r2_y1 + 64), (right_x2 - 30, r2_y1 + 64)], fill=CARD_BORDER, width=2)

    terms_text = ", ".join(slide_out.key_terms) if slide_out.key_terms else "(Core concepts)"
    f_terms = _get_font(19, bold=True)
    terms_lines = _wrap_text(terms_text, f_terms, (right_x2 - right_x1) - 60, draw)
    t_y = r2_y1 + 84
    for line in terms_lines[:3]:
        draw.text((right_x1 + 30, t_y), line, fill=TAG_TEXT_BLUE, font=f_terms)
        t_y += 30

    # Visual cue divider
    t_y = max(t_y + 15, r2_y1 + 200)
    draw.line([(right_x1 + 30, t_y), (right_x2 - 30, t_y)], fill=CARD_BORDER, width=2)
    t_y += 20

    draw.text((right_x1 + 30, t_y), "🎬 Visual Guidance", fill=TAG_TEXT_AMBER, font=f_side_hdr)
    t_y += 36
    f_va = _get_font(18, bold=False)
    va_lines = _wrap_text(slide_out.visual_action or "Highlight key points on screen.", f_va, (right_x2 - right_x1) - 60, draw)
    for line in va_lines[:4]:
        draw.text((right_x1 + 30, t_y), line, fill=TEXT_PRIMARY, font=f_va)
        t_y += 28

    # Bottom footer indicator: Progress Line
    progress_frac = section_index / float(total_sections)
    draw.rectangle([0, height - 8, int(width * progress_frac), height], fill=TOP_BAR_COLOR)

    img.save(output_path, quality=95)
    return output_path


def render_all_slides(result: PipelineResult, output_dir: str = "output/generated") -> List[str]:
    """
    Renders 1080p images for all slides:
    1. Title slide
    2. Each section slide
    Returns a list of image paths [slide_0_title.png, slide_1.png, ...].
    """
    media_dir = os.path.abspath(output_dir)
    slides_dir = os.path.join(media_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)

    rendered_images: List[str] = []

    # 1. Title slide
    title_path = os.path.join(slides_dir, "slide_0_title.png")
    render_title_slide(result.document_summary, title_path)
    rendered_images.append(title_path)

    # 2. Section slides
    total = len(result.slide_outputs)
    for idx, slide_out in enumerate(result.slide_outputs, start=1):
        slide_path = os.path.join(slides_dir, f"slide_{idx}_{slide_out.section_index}.png")
        render_section_slide(slide_out, idx, total, slide_path)
        rendered_images.append(slide_path)

    return rendered_images
