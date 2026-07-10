from __future__ import annotations

import re

from app.ai.analysis_models import (
    ClipAnalysisRequest,
    ClipAnalysisResult,
    FinalVideoReviewRequest,
    FinalVideoReviewResult,
    ProjectCreativeRequest,
    ProjectCreativeResult,
)
from app.ai.analysis_provider import AIAnalysisProvider


class MockAIAnalysisProvider(AIAnalysisProvider):
    """
    Deterministic AI replacement used for workflow development.

    This provider never contacts an external API and does not inspect
    actual video frames. It creates predictable results from metadata.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    def analyze_clip(
        self,
        request: ClipAnalysisRequest,
    ) -> ClipAnalysisResult:
        title = request.candidate.title.strip()
        media = request.media_info

        topic_match_score = self._calculate_topic_match_score(
            title=title,
            theme=request.theme,
        )

        quality_score = self._calculate_quality_score(request)
        hook_score = self._calculate_hook_score(title)

        rejection_reasons: list[str] = []
        warnings: list[str] = [
            "Mock AI provider did not inspect the actual video content."
        ]

        duration = media.duration_seconds

        if not media.exists:
            rejection_reasons.append("The local media file does not exist.")

        if not media.has_video:
            rejection_reasons.append("No video stream was detected.")

        if duration is None:
            rejection_reasons.append("The clip duration is unknown.")

        elif duration < 1.0:
            rejection_reasons.append("The clip is too short.")

        elif duration > 45.0:
            warnings.append(
                "The clip is long and may require trimming."
            )

        if topic_match_score < 4:
            rejection_reasons.append(
                "The clip does not match the requested theme closely enough."
            )

        usable = not rejection_reasons

        trim_start = None
        trim_end = None

        if (
            request.permissions.allow_trim_suggestions
            and duration is not None
            and duration > 12.0
        ):
            trim_start = 0.0
            trim_end = min(duration, 10.0)

        ranking_caption = ""

        if request.permissions.allow_ranking_captions:
            ranking_caption = self._create_ranking_caption(title)

        return ClipAnalysisResult(
            clip_id=request.clip_id,
            summary=title or "Mock clip",
            detected_theme=request.theme,
            usable=usable,
            topic_match_score=topic_match_score,
            quality_score=quality_score,
            hook_score=hook_score,
            ranking_caption=ranking_caption,
            suggested_trim_start_seconds=trim_start,
            suggested_trim_end_seconds=trim_end,
            contains_watermark=False,
            contains_embedded_text=False,
            contains_sensitive_content=request.candidate.is_nsfw,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            tags=self._extract_tokens(title),
        )

    def create_project_copy(
        self,
        request: ProjectCreativeRequest,
    ) -> ProjectCreativeResult:
        usable_analyses = [
            analysis
            for analysis in request.clip_analyses
            if analysis.usable
        ]

        ordered_analyses = sorted(
            usable_analyses,
            key=lambda analysis: (
                analysis.hook_score,
                analysis.topic_match_score,
                analysis.quality_score,
            ),
            reverse=True,
        )

        header_text = ""

        if request.permissions.allow_header_text:
            header_text = self._create_header_text(request.theme)

        ranking_captions: dict[str, str] = {}

        if request.permissions.allow_ranking_captions:
            for analysis in ordered_analyses:
                ranking_captions[analysis.clip_id] = (
                    analysis.ranking_caption
                    or "unexpected moment"
                )

        recommended_clip_order: list[str] = []

        if request.permissions.allow_clip_reordering:
            recommended_clip_order = [
                analysis.clip_id
                for analysis in ordered_analyses
            ]

        return ProjectCreativeResult(
            header_text=header_text,
            ranking_captions=ranking_captions,
            recommended_clip_order=recommended_clip_order,
            overall_theme=request.theme,
            warnings=[
                "Mock AI provider generated placeholder creative content."
            ],
        )

    def review_final_video(
        self,
        request: FinalVideoReviewRequest,
    ) -> FinalVideoReviewResult:
        media = request.media_info
        issues: list[str] = []
        recommendations: list[str] = [
            "Mock provider performed metadata-only review."
        ]

        duration = media.duration_seconds or 0.0

        if not media.exists:
            issues.append("Rendered video file does not exist.")

        if not media.has_video:
            issues.append("Rendered file has no video stream.")

        if not media.has_audio:
            issues.append("Rendered file has no audio stream.")

        if duration < 60.0:
            issues.append(
                f"Rendered video is below 60 seconds ({duration:.2f}s)."
            )

        visual_quality_ok = (
            media.has_video
            and media.width is not None
            and media.height is not None
            and media.width >= 720
            and media.height >= 1280
        )

        if not visual_quality_ok:
            issues.append(
                "Rendered video resolution is below the expected vertical-video quality."
            )

        audio_quality_ok = media.has_audio

        approved = (
            not issues
            and media.exists
            and media.has_video
            and duration >= 60.0
        )

        return FinalVideoReviewResult(
            approved_for_upload=approved,
            overall_quality_score=8 if approved else 4,
            hook_score=7 if approved else 4,
            pacing_score=7 if approved else 4,
            header_matches_content=bool(
                request.expected_header_text.strip()
            ),
            captions_match_clips=bool(
                request.expected_ranking_captions
            ),
            visual_quality_ok=visual_quality_ok,
            audio_quality_ok=audio_quality_ok,
            issues=issues,
            recommendations=recommendations,
        )

    def _calculate_topic_match_score(
        self,
        title: str,
        theme: str,
    ) -> int:
        title_tokens = set(self._extract_tokens(title))
        theme_tokens = set(self._extract_tokens(theme))

        if not theme_tokens:
            return 7

        overlap = len(title_tokens & theme_tokens)
        ratio = overlap / max(1, len(theme_tokens))

        return max(3, min(10, round(5 + ratio * 5)))

    def _calculate_quality_score(
        self,
        request: ClipAnalysisRequest,
    ) -> int:
        media = request.media_info
        score = 3

        if media.exists:
            score += 1

        if media.has_video:
            score += 2

        if media.width is not None and media.height is not None:
            if media.width >= 720 or media.height >= 1280:
                score += 2
            else:
                score += 1

        if media.fps is not None and media.fps >= 24:
            score += 1

        if media.duration_seconds is not None:
            if 2.0 <= media.duration_seconds <= 20.0:
                score += 1

        return max(0, min(10, score))

    def _calculate_hook_score(self, title: str) -> int:
        normalized = title.lower()

        high_hook_terms = {
            "instant",
            "unexpected",
            "chaos",
            "regret",
            "perfect",
            "fail",
        }

        matches = sum(
            1
            for term in high_hook_terms
            if term in normalized
        )

        return max(5, min(10, 6 + matches))

    def _create_ranking_caption(self, title: str) -> str:
        cleaned = title.strip()

        if ":" in cleaned:
            cleaned = cleaned.split(":", 1)[1].strip()

        words = cleaned.split()

        if len(words) > 6:
            words = words[:6]

        caption = " ".join(words).strip().lower()

        return caption or "unexpected moment"

    def _create_header_text(self, theme: str) -> str:
        cleaned_theme = " ".join(theme.strip().split())

        if not cleaned_theme:
            return "Moments You Need To See"

        return f"{cleaned_theme.title()} You Need To See"

    def _extract_tokens(self, value: str) -> list[str]:
        return [
            token
            for token in re.split(r"[^a-z0-9]+", value.lower())
            if len(token) >= 2
        ]