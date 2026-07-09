from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.preset_config import HeaderOverlayConfig, PresetConfig, RankingOverlayConfig
from app.core.render_plan import RenderSegment


class OverlayImageBuilder:
    """
    Builds transparent overlay images.

    Supported modules:
    - Header Overlay
    - Ranking Overlay

    Both can be enabled at the same time.
    """

    def __init__(
        self,
        width: int = 1080,
        height: int = 1920,
    ) -> None:
        self.width = width
        self.height = height

    def build_segment_overlay(
        self,
        output_path: Path,
        ranked_segments: list[RenderSegment],
        current_segment: RenderSegment,
        preset_config: PresetConfig,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        if preset_config.header_overlay.enabled:
            self._draw_header_overlay(
                draw=draw,
                style=preset_config.header_overlay,
            )

        if (
            preset_config.ranking_overlay.enabled
            and current_segment.show_ranking_overlay
        ):
            self._draw_ranking_overlay(
                draw=draw,
                ranked_segments=ranked_segments,
                style=preset_config.ranking_overlay,
                header_style=preset_config.header_overlay,
                current_rank_index=current_segment.rank_index,
            )

        image.save(output_path)
        return output_path

    def _draw_header_overlay(
        self,
        draw: ImageDraw.ImageDraw,
        style: HeaderOverlayConfig,
    ) -> None:
        if not style.text.strip():
            return

        background_color = self._hex_to_rgba(
            style.background_color,
            alpha=max(0, min(style.background_opacity, 255)),
        )

        draw.rectangle(
            (0, 0, self.width, style.bar_height),
            fill=background_color,
        )

        font = self._load_font(
            size=style.font_size,
            bold=style.bold,
            custom_font_path=style.font_path,
        )

        words = style.text.strip().split()

        if not words:
            return

        lines = self._wrap_words(
            draw=draw,
            words=words,
            font=font,
            max_width=self.width - (style.horizontal_padding * 2),
        )

        line_metrics = [
            self._get_text_size(draw=draw, text=" ".join(line), font=font)
            for line in lines
        ]

        total_text_height = sum(height for _width, height in line_metrics)
        total_text_height += max(0, len(lines) - 1) * style.line_spacing

        current_y = style.y_offset

        if total_text_height < style.bar_height:
            current_y = max(
                style.y_offset,
                (style.bar_height - total_text_height) // 2,
            )

        global_word_index = 0

        for line, (line_width, line_height) in zip(lines, line_metrics):
            if style.align == "left":
                current_x = style.horizontal_padding
            elif style.align == "right":
                current_x = self.width - style.horizontal_padding - line_width
            else:
                current_x = (self.width - line_width) // 2

            for word_index_in_line, word in enumerate(line):
                word_color = self._get_header_word_color(
                    word_index=global_word_index,
                    style=style,
                )

                self._draw_text(
                    draw=draw,
                    position=(current_x, current_y),
                    text=word,
                    font=font,
                    fill=word_color,
                    stroke_width=style.stroke_width,
                    stroke_color=self._hex_to_rgba(style.stroke_color, alpha=255),
                )

                word_width, _word_height = self._get_text_size(
                    draw=draw,
                    text=word,
                    font=font,
                )

                current_x += word_width

                if word_index_in_line < len(line) - 1:
                    space_width, _space_height = self._get_text_size(
                        draw=draw,
                        text=" ",
                        font=font,
                    )
                    current_x += space_width

                global_word_index += 1

            current_y += line_height + style.line_spacing

    def _draw_ranking_overlay(
        self,
        draw: ImageDraw.ImageDraw,
        ranked_segments: list[RenderSegment],
        style: RankingOverlayConfig,
        header_style: HeaderOverlayConfig,
        current_rank_index: int | None = None,
    ) -> None:
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

        effective_y_start = style.y_start

        if header_style.enabled:
            effective_y_start = max(
                style.y_start,
                header_style.bar_height + 35,
            )

        for row_index, segment in enumerate(ranked_segments):
            rank = segment.rank_index

            if rank is None:
                continue

            y = effective_y_start + row_index * style.line_height

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

    def _wrap_words(
        self,
        draw: ImageDraw.ImageDraw,
        words: list[str],
        font: ImageFont.ImageFont,
        max_width: int,
    ) -> list[list[str]]:
        lines: list[list[str]] = []
        current_line: list[str] = []

        for word in words:
            test_line = [*current_line, word]
            test_text = " ".join(test_line)
            test_width, _test_height = self._get_text_size(
                draw=draw,
                text=test_text,
                font=font,
            )

            if test_width <= max_width or not current_line:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = [word]

        if current_line:
            lines.append(current_line)

        return lines

    def _get_header_word_color(
        self,
        word_index: int,
        style: HeaderOverlayConfig,
    ) -> tuple[int, int, int, int]:
        color_hex = (
            style.word_colors.get(str(word_index))
            or style.default_word_color
            or "#FFFFFF"
        )

        return self._hex_to_rgba(color_hex)

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

    def _draw_text(
        self,
        draw: ImageDraw.ImageDraw,
        position: tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        fill: tuple[int, int, int, int],
        stroke_width: int,
        stroke_color: tuple[int, int, int, int],
    ) -> None:
        draw.text(
            position,
            text,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )

    def _get_text_size(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
    ) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

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