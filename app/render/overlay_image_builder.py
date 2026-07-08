from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.preset_config import RankingOverlayConfig
from app.core.render_plan import RenderSegment


class OverlayImageBuilder:
    """
    Creates transparent PNG overlays for ranking videos.

    Behavior:
    - all ranking numbers are visible from the start
    - captions reveal progressively
    - visual style comes from the preset config
    """

    def __init__(
        self,
        width: int = 1080,
        height: int = 1920,
    ) -> None:
        self.width = width
        self.height = height

    def build_ranking_overlay(
        self,
        output_path: Path,
        ranked_segments: list[RenderSegment],
        style: RankingOverlayConfig,
        current_rank_index: int | None = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        number_font = self._load_font(
            size=style.number_font_size,
            bold=True,
            custom_font_path=style.number_font_path,
        )

        caption_font = self._load_font(
            size=style.caption_font_size,
            bold=False,
            custom_font_path=style.caption_font_path,
        )

        caption_color = self._hex_to_rgba(style.caption_color)
        stroke_color = self._hex_to_rgba(style.stroke_color, alpha=220)
        shadow_color = self._hex_to_rgba(style.shadow_color, alpha=180)

        for row_index, segment in enumerate(ranked_segments):
            rank = segment.rank_index

            if rank is None:
                continue

            y = style.y_start + row_index * style.line_height

            number_text = f"{rank}."
            number_color = self._get_number_color(rank=rank, style=style)

            self._draw_text_with_shadow(
                draw=draw,
                position=(style.x_number, y),
                text=number_text,
                font=number_font,
                fill=number_color,
                stroke_width=style.number_stroke_width,
                stroke_color=stroke_color,
                shadow_color=shadow_color,
                shadow_offset=(style.shadow_offset_x, style.shadow_offset_y),
            )

            should_show_caption = (
                current_rank_index is not None
                and rank <= current_rank_index
            )

            if should_show_caption:
                caption_text = segment.caption.strip() if segment.caption.strip() else "..."

                self._draw_text_with_shadow(
                    draw=draw,
                    position=(style.x_caption, y + 13),
                    text=caption_text,
                    font=caption_font,
                    fill=caption_color,
                    stroke_width=style.caption_stroke_width,
                    stroke_color=stroke_color,
                    shadow_color=shadow_color,
                    shadow_offset=(style.shadow_offset_x, style.shadow_offset_y),
                )

        image.save(output_path)
        return output_path

    def _get_number_color(
        self,
        rank: int,
        style: RankingOverlayConfig,
    ) -> tuple[int, int, int, int]:
        color_hex = (
            style.number_colors.get(str(rank))
            or style.number_colors.get("default")
            or "#FFD700"
        )

        return self._hex_to_rgba(color_hex)

    def _draw_text_with_shadow(
        self,
        draw: ImageDraw.ImageDraw,
        position: tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        fill: tuple[int, int, int, int],
        stroke_width: int,
        stroke_color: tuple[int, int, int, int],
        shadow_color: tuple[int, int, int, int],
        shadow_offset: tuple[int, int],
    ) -> None:
        x, y = position
        shadow_x, shadow_y = shadow_offset

        draw.text(
            (x + shadow_x, y + shadow_y),
            text,
            font=font,
            fill=shadow_color,
        )

        draw.text(
            (x, y),
            text,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )

    def _load_font(
        self,
        size: int,
        bold: bool,
        custom_font_path: str,
    ) -> ImageFont.ImageFont:
        if custom_font_path.strip():
            custom_path = Path(custom_font_path.strip())

            if custom_path.exists():
                return ImageFont.truetype(str(custom_path), size=size)

        possible_paths = []

        if bold:
            possible_paths.extend(
                [
                    Path("assets/fonts/Inter-Bold.ttf"),
                    Path("C:/Windows/Fonts/arialbd.ttf"),
                    Path("C:/Windows/Fonts/segoeuib.ttf"),
                    Path("C:/Windows/Fonts/impact.ttf"),
                ]
            )
        else:
            possible_paths.extend(
                [
                    Path("assets/fonts/Inter-Regular.ttf"),
                    Path("C:/Windows/Fonts/arial.ttf"),
                    Path("C:/Windows/Fonts/segoeui.ttf"),
                    Path("C:/Windows/Fonts/calibri.ttf"),
                ]
            )

        for font_path in possible_paths:
            if font_path.exists():
                return ImageFont.truetype(str(font_path), size=size)

        return ImageFont.load_default()

    def _hex_to_rgba(
        self,
        value: str,
        alpha: int = 255,
    ) -> tuple[int, int, int, int]:
        cleaned = value.strip().lstrip("#")

        if len(cleaned) == 3:
            cleaned = "".join(character * 2 for character in cleaned)

        if len(cleaned) != 6:
            return (255, 255, 255, alpha)

        try:
            red = int(cleaned[0:2], 16)
            green = int(cleaned[2:4], 16)
            blue = int(cleaned[4:6], 16)
        except ValueError:
            return (255, 255, 255, alpha)

        return (red, green, blue, alpha)