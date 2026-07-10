from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from typing import Any

from app.ai.clip_analysis_request_factory import (
    ClipAnalysisPresetContext,
)
from app.planning.source_plan_models import (
    SourceProjectPlan,
    ThemeDerivationMethod,
)
from app.sources.source_models import (
    SourceCandidate,
    SourceProfile,
)


class SourceProjectPlanner:
    """
    Creates one shared project plan before individual clips are analyzed.

    The planner is deterministic and free. It gives ClipFactory a stable
    fallback theme even before an AI-based theme-refinement step runs.
    """

    GENERIC_COMMUNITY_TERMS = {
        "video",
        "videos",
        "clip",
        "clips",
        "funny",
        "meme",
        "memes",
        "unexpected",
        "interesting",
        "random",
        "shorts",
        "reddit",
    }

    TITLE_STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "his",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "just",
        "my",
        "of",
        "on",
        "or",
        "our",
        "she",
        "so",
        "that",
        "the",
        "their",
        "they",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "with",
        "you",
        "your",
    }

    def create_plan(
        self,
        source_profile: SourceProfile,
        candidates: Sequence[SourceCandidate],
        preset_context: ClipAnalysisPresetContext,
    ) -> SourceProjectPlan:
        candidate_list = list(candidates)

        community_theme = self._humanize_identifier(
            source_profile.community
        )

        title_keywords = self._extract_title_keywords(
            candidates=candidate_list,
            community_theme=community_theme,
        )

        (
            theme,
            theme_derivation,
        ) = self._derive_theme(
            source_profile=source_profile,
            community_theme=community_theme,
            title_keywords=title_keywords,
        )

        candidate_ids = [
            self._candidate_id(candidate)
            for candidate in candidate_list
            if self._candidate_id(candidate)
        ]

        warnings: list[str] = []

        if not candidate_list:
            warnings.append(
                "No source candidates were available while "
                "creating the project plan."
            )

        if (
            theme_derivation
            == ThemeDerivationMethod.FALLBACK
        ):
            warnings.append(
                "The project theme could not be derived from "
                "the source and fell back to a generic value."
            )

        project_id = self._project_id(
            source_profile=source_profile,
            preset_context=preset_context,
        )

        return SourceProjectPlan(
            project_id=project_id,
            project_name=(
                f"{source_profile.name} - "
                f"{preset_context.preset_id}"
            ),
            source_profile_id=source_profile.id,
            source_community=source_profile.community,
            preset_id=preset_context.preset_id,
            target_platform=(
                preset_context.target_platform
            ),
            video_format=preset_context.video_format,
            theme=theme,
            theme_derivation=theme_derivation,
            theme_keywords=title_keywords,
            candidate_ids=candidate_ids,
            candidate_count=len(candidate_list),
            warnings=warnings,
        )

    def _derive_theme(
        self,
        source_profile: SourceProfile,
        community_theme: str,
        title_keywords: list[str],
    ) -> tuple[str, ThemeDerivationMethod]:
        explicit_hint = str(
            getattr(
                source_profile,
                "theme_hint",
                "",
            )
            or ""
        ).strip()

        if explicit_hint:
            return (
                explicit_hint,
                ThemeDerivationMethod.EXPLICIT_HINT,
            )

        community_tokens = set(
            community_theme.split()
        )

        community_is_generic = bool(
            community_tokens
        ) and community_tokens.issubset(
            self.GENERIC_COMMUNITY_TERMS
        )

        if community_theme and not community_is_generic:
            return (
                community_theme,
                ThemeDerivationMethod.COMMUNITY_NAME,
            )

        if community_theme and title_keywords:
            keyword_suffix = " ".join(
                title_keywords[:2]
            )

            return (
                f"{community_theme} {keyword_suffix}".strip(),
                ThemeDerivationMethod.COMMUNITY_AND_TITLES,
            )

        if title_keywords:
            return (
                " ".join(title_keywords[:3]),
                ThemeDerivationMethod.CANDIDATE_TITLES,
            )

        if community_theme:
            return (
                community_theme,
                ThemeDerivationMethod.COMMUNITY_NAME,
            )

        return (
            "general short-form clips",
            ThemeDerivationMethod.FALLBACK,
        )

    def _extract_title_keywords(
        self,
        candidates: list[SourceCandidate],
        community_theme: str,
    ) -> list[str]:
        excluded_words = (
            self.TITLE_STOP_WORDS
            | self.GENERIC_COMMUNITY_TERMS
            | set(community_theme.split())
        )

        word_counts: Counter[str] = Counter()

        for candidate in candidates:
            title = str(
                getattr(
                    candidate,
                    "title",
                    "",
                )
                or ""
            )

            words = re.findall(
                r"[A-Za-z0-9']+",
                title.lower(),
            )

            for word in words:
                if len(word) < 3:
                    continue

                if word in excluded_words:
                    continue

                if word.isdigit():
                    continue

                word_counts[word] += 1

        ordered_keywords = sorted(
            word_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )

        return [
            keyword
            for keyword, _count in ordered_keywords[:8]
        ]

    def _candidate_id(
        self,
        candidate: SourceCandidate,
    ) -> str:
        for field_name in (
            "candidate_id",
            "external_post_id",
        ):
            value = str(
                getattr(
                    candidate,
                    field_name,
                    "",
                )
                or ""
            ).strip()

            if value:
                return value

        return ""

    def _project_id(
        self,
        source_profile: SourceProfile,
        preset_context: ClipAnalysisPresetContext,
    ) -> str:
        raw_value = (
            f"{source_profile.platform.value}_"
            f"{source_profile.community}_"
            f"{preset_context.preset_id}"
        )

        normalized_value = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            raw_value,
        )

        return normalized_value.strip("_").lower()

    def _humanize_identifier(
        self,
        value: Any,
    ) -> str:
        normalized_value = str(
            value or ""
        ).strip()

        normalized_value = re.sub(
            r"^r/",
            "",
            normalized_value,
            flags=re.IGNORECASE,
        )

        normalized_value = re.sub(
            r"(?<=[a-z0-9])(?=[A-Z])",
            " ",
            normalized_value,
        )

        normalized_value = re.sub(
            r"[_\-]+",
            " ",
            normalized_value,
        )

        normalized_value = re.sub(
            r"\s+",
            " ",
            normalized_value,
        ).strip()

        return normalized_value.lower()