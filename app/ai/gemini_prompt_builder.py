from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.ai.analysis_models import (
    ClipAnalysisRequest,
    FinalVideoReviewRequest,
    ProjectCreativeRequest,
)
from app.ai.gemini_config import GeminiConfig
from app.ai.usage_models import AIOperationType


class GeminiPromptPackage(BaseModel):
    """
    Provider-ready prompt generated for one Gemini operation.

    The prompt version is included so prompt changes can invalidate old
    cached results through the provider identity.
    """

    operation_type: AIOperationType
    prompt_version: str
    text: str = Field(min_length=1)


class GeminiPromptBuilder:
    """
    Builds deterministic Gemini prompts from ClipFactory request models.

    Local filesystem paths and other machine-specific fields are removed
    before request metadata is embedded in the prompt.
    """

    PRIVATE_FIELD_NAMES = {
        "local_path",
        "video_path",
        "resolved_path",
        "download_path",
        "cache_path",
        "api_key",
        "api_key_environment_variable",
    }

    PRIVATE_FIELD_SUFFIXES = (
        "_local_path",
        "_filesystem_path",
    )

    def __init__(self, config: GeminiConfig) -> None:
        self.config = config

    def build_clip_analysis(
        self,
        request: ClipAnalysisRequest,
    ) -> GeminiPromptPackage:
        payload = self._model_payload(request)

        return self.build_clip_analysis_from_payload(payload)

    def build_project_creative(
        self,
        request: ProjectCreativeRequest,
    ) -> GeminiPromptPackage:
        payload = self._model_payload(request)

        return self.build_project_creative_from_payload(payload)

    def build_final_video_review(
        self,
        request: FinalVideoReviewRequest,
    ) -> GeminiPromptPackage:
        payload = self._model_payload(request)

        return self.build_final_video_review_from_payload(payload)

    def build_clip_analysis_from_payload(
        self,
        payload: dict[str, Any],
    ) -> GeminiPromptPackage:
        sanitized_payload = self._sanitize_value(payload)
        context_json = self._context_json(sanitized_payload)

        prompt = f"""
You are ClipFactory's video clip analysis engine.

Analyze the supplied video using both its visible and audible content.
Use the metadata below only as additional context. Do not claim to have
observed something unless it is actually present in the supplied media.

Your task:
1. Summarize the clip accurately and concisely.
2. Identify its central theme.
3. Determine whether it is useful for the requested short-form format.
4. Score topic match, technical quality, and opening hook honestly.
5. Write one short ranking caption when the clip is usable.
6. Suggest trim points only when trimming clearly improves the clip.
7. Detect visible watermarks, embedded text, and sensitive content.
8. Add concrete rejection reasons and warnings where appropriate.

Scoring rules:
- Use the full 0 to 10 range.
- A high topic score requires genuine thematic relevance.
- A high quality score requires watchable visual and audio quality.
- A high hook score requires an engaging opening or immediate payoff.
- Do not inflate scores merely to make a clip usable.

Ranking-caption rules:
- Keep it concise and immediately understandable.
- Prefer approximately 2 to 7 words.
- Describe the clip's distinctive moment rather than using a generic label.
- Follow the requested caption style when one is provided.
- Do not include numbering; ClipFactory renders ranking numbers separately.
- Do not include hashtags, quotation marks, emojis, or trailing punctuation.

Workflow boundaries:
- Content quality and media rights are separate concerns.
- Do not reject an otherwise suitable clip merely because rights status is
  unknown.
- Do not modify preset styling, fonts, colors, positions, transitions,
  duration rules, or ranking behavior.
- Respect every AI permission included in the request.
- Return only fields required by the response schema.

ClipFactory request context:
{context_json}
""".strip()

        return GeminiPromptPackage(
            operation_type=AIOperationType.CLIP_ANALYSIS,
            prompt_version=(
                self.config.clip_analysis.prompt_version
            ),
            text=prompt,
        )

    def build_project_creative_from_payload(
        self,
        payload: dict[str, Any],
    ) -> GeminiPromptPackage:
        sanitized_payload = self._sanitize_value(payload)
        context_json = self._context_json(sanitized_payload)

        prompt = f"""
You are ClipFactory's short-form creative copy engine.

The supplied context contains a project specification and previously
validated clip analyses. Generate only the content fields permitted by the
request.

Header rules:
- Make the header concise, specific, and natural.
- Clearly communicate the shared theme of the selected clips.
- Avoid vague filler such as "You Won't Believe This".
- Do not use hashtags, quotation marks, or trailing punctuation.
- Do not mention Reddit unless the project explicitly requires it.

Ranking-caption rules:
- Produce one caption for each usable selected clip.
- Keep captions approximately 2 to 7 words.
- Make every caption distinct and tied to that clip's actual event.
- Do not include ranking numbers; ClipFactory renders them separately.
- Follow the requested caption style.
- Avoid repeated sentence structures and generic filler.

Permission and preset rules:
- Preset styling is locked.
- Do not propose changes to fonts, colors, layout, positions, transitions,
  animation, duration limits, or platform rules.
- If clip reordering is not permitted, recommended_clip_order must be empty.
- If header generation is not permitted, do not invent a replacement header.
- If ranking-caption generation is not permitted, do not invent captions.
- Do not add fields outside the response schema.

Return content that is suitable for the specified target platform and video
format while remaining truthful to the analyzed clips.

ClipFactory project context:
{context_json}
""".strip()

        return GeminiPromptPackage(
            operation_type=AIOperationType.PROJECT_CREATIVE,
            prompt_version=(
                self.config.project_creative.prompt_version
            ),
            text=prompt,
        )

    def build_final_video_review_from_payload(
        self,
        payload: dict[str, Any],
    ) -> GeminiPromptPackage:
        sanitized_payload = self._sanitize_value(payload)
        context_json = self._context_json(sanitized_payload)

        prompt = f"""
You are ClipFactory's final rendered-video reviewer.

Review the supplied completed video as a viewer would experience it. Assess
the actual rendered result rather than merely repeating project metadata.

Check:
1. Whether the opening is immediately understandable and engaging.
2. Whether the header is readable and matches the actual video theme.
3. Whether ranking captions accurately describe their clips.
4. Whether clip order and pacing remain coherent.
5. Whether transitions, cuts, audio, and overlays appear technically clean.
6. Whether text is cropped, obscured, mistimed, or difficult to read.
7. Whether the final video contains obvious blank frames, frozen segments,
   duplicated clips, broken audio, or unexpected silence.
8. Whether any visible watermark, embedded text, or sensitive content needs
   human review.
9. Whether the final result is ready to publish.

Review boundaries:
- Do not redesign the preset.
- Do not recommend arbitrary font, color, position, or transition changes.
- Report a preset-related issue only when it causes a concrete defect in the
  rendered video.
- Media-rights approval is handled by a separate workflow.
- Unknown rights status alone is not a video-quality failure.
- Be specific about every blocking issue.
- Return only fields required by the response schema.

ClipFactory final-review context:
{context_json}
""".strip()

        return GeminiPromptPackage(
            operation_type=AIOperationType.FINAL_VIDEO_REVIEW,
            prompt_version=(
                self.config.final_video_review.prompt_version
            ),
            text=prompt,
        )

    def _model_payload(
        self,
        model: BaseModel,
    ) -> dict[str, Any]:
        payload = model.model_dump(mode="json")

        sanitized_payload = self._sanitize_value(payload)

        if not isinstance(sanitized_payload, dict):
            raise TypeError(
                "Gemini prompt request payload must be an object."
            )

        return sanitized_payload

    def _sanitize_value(
        self,
        value: Any,
    ) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}

            for raw_key, child_value in value.items():
                key = str(raw_key)

                if self._is_private_field(key):
                    continue

                sanitized[key] = self._sanitize_value(
                    child_value
                )

            return sanitized

        if isinstance(value, list):
            return [
                self._sanitize_value(item)
                for item in value
            ]

        if isinstance(value, tuple):
            return [
                self._sanitize_value(item)
                for item in value
            ]

        return value

    def _is_private_field(self, field_name: str) -> bool:
        normalized_name = field_name.strip().lower()

        if normalized_name in self.PRIVATE_FIELD_NAMES:
            return True

        return normalized_name.endswith(
            self.PRIVATE_FIELD_SUFFIXES
        )

    def _context_json(
        self,
        payload: dict[str, Any],
    ) -> str:
        return json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )