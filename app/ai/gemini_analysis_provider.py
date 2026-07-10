from __future__ import annotations

import mimetypes
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel

from app.ai.ai_budget_guard import (
    AIBudgetExceededError,
    AIBudgetGuard,
)
from app.ai.ai_usage_ledger import AIUsageLedger
from app.ai.analysis_models import (
    ClipAnalysisRequest,
    ClipAnalysisResult,
    FinalVideoReviewRequest,
    FinalVideoReviewResult,
    ProjectCreativeRequest,
    ProjectCreativeResult,
)
from app.ai.analysis_provider import (
    AIAnalysisProvider,
    AIAnalysisProviderError,
)
from app.ai.gemini_config import (
    GeminiConfig,
    GeminiOperationConfig,
    load_gemini_config,
)
from app.ai.gemini_prompt_builder import (
    GeminiPromptBuilder,
    GeminiPromptPackage,
)
from app.ai.gemini_usage import (
    GeminiUsageSnapshot,
    calculate_gemini_usage_cost,
)
from app.ai.request_estimator import (
    GeminiRequestEstimateBreakdown,
    GeminiRequestEstimator,
)
from app.ai.usage_models import (
    AIOperationType,
    AIUsageRecord,
)


ResultModel = TypeVar(
    "ResultModel",
    bound=BaseModel,
)


class GeminiAnalysisProvider(AIAnalysisProvider):
    """
    Real Gemini implementation of ClipFactory's AI provider contract.

    Every request follows this sequence:

    1. Build deterministic prompt.
    2. Estimate tokens and cost.
    3. Check AI budget.
    4. Upload media when required.
    5. Wait for file processing.
    6. Request structured output.
    7. Record actual usage.
    8. Delete uploaded media.
    """

    FILE_POLL_INTERVAL_SECONDS = 2.0

    def __init__(
        self,
        config: GeminiConfig,
        budget_guard: AIBudgetGuard,
        usage_ledger: AIUsageLedger,
        job_id: str = "",
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.budget_guard = budget_guard
        self.usage_ledger = usage_ledger
        self.job_id = job_id.strip()
        self.log_callback = log_callback

        self.prompt_builder = GeminiPromptBuilder(config)
        self.request_estimator = GeminiRequestEstimator(config)

    @classmethod
    def from_config_files(
        cls,
        gemini_config_path: Path = Path(
            "config/gemini.json"
        ),
        budget_config_path: Path = Path(
            "config/ai_budget.json"
        ),
        ledger_path: Path = Path(
            "data/ai/usage_ledger.json"
        ),
        job_id: str = "",
        log_callback: Callable[[str], None] | None = None,
    ) -> "GeminiAnalysisProvider":
        config = load_gemini_config(
            gemini_config_path
        )

        ledger = AIUsageLedger(
            ledger_path=ledger_path
        )

        budget_guard = AIBudgetGuard.from_config_file(
            config_path=budget_config_path,
            ledger=ledger,
        )

        return cls(
            config=config,
            budget_guard=budget_guard,
            usage_ledger=ledger,
            job_id=job_id,
            log_callback=log_callback,
        )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def cache_identity(self) -> str:
        return self.config.provider_identity

    def analyze_clip(
        self,
        request: ClipAnalysisRequest,
    ) -> ClipAnalysisResult:
        prompt = self.prompt_builder.build_clip_analysis(
            request
        )

        duration_seconds = self._safe_float(
            getattr(
                request.media_info,
                "duration_seconds",
                0.0,
            )
        )

        has_audio = bool(
            getattr(
                request.media_info,
                "has_audio",
                False,
            )
        )

        return self._run_operation(
            prompt=prompt,
            result_model=ClipAnalysisResult,
            request_label=f"clip_analysis:{request.clip_id}",
            fallback_job_id=request.clip_id,
            media_path=Path(request.local_path),
            video_seconds=duration_seconds,
            audio_seconds=(
                duration_seconds
                if has_audio
                else 0.0
            ),
            has_video=True,
            has_audio=has_audio,
        )

    def create_project_copy(
        self,
        request: ProjectCreativeRequest,
    ) -> ProjectCreativeResult:
        prompt = (
            self.prompt_builder.build_project_creative(
                request
            )
        )

        return self._run_operation(
            prompt=prompt,
            result_model=ProjectCreativeResult,
            request_label=(
                f"project_creative:{request.project_name}"
            ),
            fallback_job_id=request.project_name,
            has_video=False,
            has_audio=False,
        )

    def review_final_video(
        self,
        request: FinalVideoReviewRequest,
    ) -> FinalVideoReviewResult:
        prompt = (
            self.prompt_builder.build_final_video_review(
                request
            )
        )

        duration_seconds = self._extract_duration(
            request
        )

        has_audio = self._extract_has_audio(
            request
        )

        return self._run_operation(
            prompt=prompt,
            result_model=FinalVideoReviewResult,
            request_label=(
                f"final_video_review:{request.project_name}"
            ),
            fallback_job_id=request.project_name,
            media_path=Path(request.video_path),
            video_seconds=duration_seconds,
            audio_seconds=(
                duration_seconds
                if has_audio
                else 0.0
            ),
            has_video=True,
            has_audio=has_audio,
        )

    def _run_operation(
        self,
        prompt: GeminiPromptPackage,
        result_model: type[ResultModel],
        request_label: str,
        fallback_job_id: str,
        media_path: Path | None = None,
        video_seconds: float = 0.0,
        audio_seconds: float = 0.0,
        has_video: bool = False,
        has_audio: bool = False,
    ) -> ResultModel:
        self._ensure_enabled()

        job_id = self._resolved_job_id(
            fallback_job_id
        )

        estimate = (
            self.request_estimator.estimate_request(
                operation_type=prompt.operation_type,
                text_content=prompt.text,
                job_id=job_id,
                request_label=request_label,
                video_seconds=video_seconds,
                audio_seconds=audio_seconds,
                has_video=has_video,
                has_audio=has_audio,
            )
        )

        self._log_lines(
            estimate.to_log_lines()
        )

        try:
            decision = self.budget_guard.ensure_allowed(
                estimate.budget_estimate
            )
        except AIBudgetExceededError:
            raise

        self._log_lines(
            decision.to_log_lines()
        )

        api_key = self._get_api_key()
        client = genai.Client(api_key=api_key)

        uploaded_file: Any | None = None

        try:
            if media_path is not None:
                uploaded_file = self._upload_video(
                    client=client,
                    media_path=media_path,
                    operation_type=prompt.operation_type,
                )

                interaction_input: str | list[dict[str, Any]] = [
                    {
                        "type": "video",
                        "uri": uploaded_file.uri,
                        "mime_type": uploaded_file.mime_type,
                        "resolution": (
                            self.config.media_resolution.value
                        ),
                    },
                    {
                        "type": "text",
                        "text": prompt.text,
                    },
                ]
            else:
                interaction_input = prompt.text

            operation_config = self._operation_config(
                prompt.operation_type
            )

            self._log(
                "Sending Gemini interaction: "
                f"{request_label}"
            )

            interaction = client.interactions.create(
                model=self.config.model,
                input=interaction_input,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": result_model.model_json_schema(),
                },
                generation_config={
                    "max_output_tokens": (
                        operation_config
                        .output_token_reserve
                    ),
                },
                store=self.config.store_interactions,
                timeout=self.config.request_timeout_seconds,
            )

            interaction_data = interaction.model_dump(
                mode="json",
                exclude_none=True,
            )

            self._record_usage(
                interaction_data=interaction_data,
                estimate=estimate,
                prompt=prompt,
                job_id=job_id,
                request_label=request_label,
                video_seconds=video_seconds,
                audio_seconds=audio_seconds,
            )

            if not interaction.output_text:
                raise AIAnalysisProviderError(
                    "Gemini returned no structured output text."
                )

            result = result_model.model_validate_json(
                interaction.output_text
            )

            self._log(
                "Gemini interaction completed: "
                f"{request_label}"
            )

            return result

        except AIBudgetExceededError:
            raise
        except AIAnalysisProviderError:
            raise
        except Exception as error:
            raise AIAnalysisProviderError(
                "Gemini operation failed for "
                f"'{request_label}': {error}"
            ) from error
        finally:
            if uploaded_file is not None:
                self._delete_uploaded_file(
                    client=client,
                    uploaded_file=uploaded_file,
                )

            try:
                client.close()
            except Exception as error:
                self._log(
                    "Warning: Gemini client cleanup failed: "
                    f"{error}"
                )

    def _upload_video(
        self,
        client: Any,
        media_path: Path,
        operation_type: AIOperationType,
    ) -> Any:
        expanded_path = media_path.expanduser()

        if not expanded_path.exists():
            raise FileNotFoundError(
                f"Video file was not found: {expanded_path}"
            )

        if not expanded_path.is_file():
            raise ValueError(
                f"Video path is not a file: {expanded_path}"
            )

        mime_type = (
            mimetypes.guess_type(
                expanded_path.name
            )[0]
            or "video/mp4"
        )

        if not mime_type.startswith("video/"):
            raise ValueError(
                "Gemini media input must be a video file. "
                f"Detected MIME type: {mime_type}"
            )

        self._log(
            "Uploading selected video to Gemini Files API."
        )

        uploaded_file = client.files.upload(
            file=str(expanded_path),
            config={
                "mime_type": mime_type,
                "display_name": (
                    f"clipfactory-"
                    f"{operation_type.value}"
                ),
            },
        )

        if not getattr(
            uploaded_file,
            "name",
            None,
        ):
            raise AIAnalysisProviderError(
                "Gemini upload returned no file name."
            )

        return self._wait_for_uploaded_file(
            client=client,
            uploaded_file=uploaded_file,
        )

    def _wait_for_uploaded_file(
        self,
        client: Any,
        uploaded_file: Any,
    ) -> Any:
        deadline = (
            time.monotonic()
            + self.config.file_processing_timeout_seconds
        )

        current_file = uploaded_file
        last_state = ""

        while True:
            state = self._file_state_name(
                getattr(
                    current_file,
                    "state",
                    None,
                )
            )

            if state != last_state:
                self._log(
                    "Gemini file state: "
                    f"{state or 'UNKNOWN'}"
                )
                last_state = state

            if state == "ACTIVE":
                if not getattr(
                    current_file,
                    "uri",
                    None,
                ):
                    raise AIAnalysisProviderError(
                        "Gemini file became active but "
                        "returned no URI."
                    )

                if not getattr(
                    current_file,
                    "mime_type",
                    None,
                ):
                    raise AIAnalysisProviderError(
                        "Gemini file became active but "
                        "returned no MIME type."
                    )

                return current_file

            if state == "FAILED":
                raise AIAnalysisProviderError(
                    "Gemini failed to process the uploaded video."
                )

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Gemini file processing exceeded "
                    f"{self.config.file_processing_timeout_seconds:.0f} "
                    "seconds."
                )

            time.sleep(
                self.FILE_POLL_INTERVAL_SECONDS
            )

            current_file = client.files.get(
                name=uploaded_file.name
            )

    def _delete_uploaded_file(
        self,
        client: Any,
        uploaded_file: Any,
    ) -> None:
        file_name = getattr(
            uploaded_file,
            "name",
            None,
        )

        if not file_name:
            return

        try:
            client.files.delete(
                name=file_name
            )

            self._log(
                "Uploaded Gemini file was deleted."
            )
        except Exception as error:
            self._log(
                "Warning: Uploaded Gemini file could not "
                f"be deleted immediately: {error}"
            )

    def _record_usage(
        self,
        interaction_data: dict[str, Any],
        estimate: GeminiRequestEstimateBreakdown,
        prompt: GeminiPromptPackage,
        job_id: str,
        request_label: str,
        video_seconds: float,
        audio_seconds: float,
    ) -> None:
        request_id = str(
            interaction_data.get("id", "")
        )

        try:
            usage = (
                GeminiUsageSnapshot
                .from_interaction_data(
                    interaction_data
                )
            )

            cost = calculate_gemini_usage_cost(
                usage=usage,
                config=self.config,
                embedded_audio_seconds=audio_seconds,
                has_embedded_audio=audio_seconds > 0,
            )

            usage_record = AIUsageRecord(
                provider_identity=(
                    estimate.provider_identity
                ),
                operation_type=prompt.operation_type,
                job_id=job_id,
                request_id=request_id,
                input_tokens=usage.total_input_tokens,
                output_tokens=usage.total_output_tokens,
                cached_input_tokens=(
                    usage.total_cached_tokens
                ),
                thinking_tokens=(
                    usage.total_thought_tokens
                ),
                video_seconds=max(
                    0.0,
                    video_seconds,
                ),
                audio_seconds=max(
                    0.0,
                    audio_seconds,
                ),
                estimated_cost_usd=(
                    estimate.estimated_total_cost_usd
                ),
                actual_cost_usd=cost.total_cost_usd,
                metadata={
                    "request_label": request_label,
                    "model": self.config.model,
                    "prompt_version": (
                        prompt.prompt_version
                    ),
                    "media_resolution": (
                        self.config
                        .media_resolution
                        .value
                    ),
                    "text_input_tokens": (
                        usage.text_input_tokens
                    ),
                    "image_input_tokens": (
                        usage.image_input_tokens
                    ),
                    "video_input_tokens": (
                        usage.video_input_tokens
                    ),
                    "audio_input_tokens": (
                        usage.audio_input_tokens
                    ),
                    "priced_audio_input_tokens": (
                        cost.priced_audio_input_tokens
                    ),
                    "audio_token_source": (
                        cost.audio_token_source
                    ),
                    "other_input_tokens": (
                        usage.other_input_tokens
                    ),
                    "tool_use_tokens": (
                        usage.total_tool_use_tokens
                    ),
                    "cost_basis": (
                        "calculated_from_actual_usage_tokens"
                    ),
                },
            )

            self.usage_ledger.record_usage(
                usage_record
            )

            self._log_lines(
                usage.to_log_lines()
            )
            self._log_lines(
                cost.to_log_lines()
            )

        except Exception as error:
            fallback_record = AIUsageRecord(
                provider_identity=(
                    estimate.provider_identity
                ),
                operation_type=prompt.operation_type,
                job_id=job_id,
                request_id=request_id,
                input_tokens=(
                    estimate.total_input_tokens
                ),
                output_tokens=0,
                thinking_tokens=0,
                video_seconds=max(
                    0.0,
                    video_seconds,
                ),
                audio_seconds=max(
                    0.0,
                    audio_seconds,
                ),
                estimated_cost_usd=(
                    estimate.estimated_total_cost_usd
                ),
                actual_cost_usd=None,
                metadata={
                    "request_label": request_label,
                    "model": self.config.model,
                    "prompt_version": (
                        prompt.prompt_version
                    ),
                    "media_resolution": (
                        self.config
                        .media_resolution
                        .value
                    ),
                    "cost_basis": (
                        "fallback_estimate"
                    ),
                    "usage_extraction_error": str(error),
                },
            )

            self.usage_ledger.record_usage(
                fallback_record
            )

            self._log(
                "Warning: Actual Gemini usage could not be "
                "parsed. The conservative estimate was "
                f"recorded instead: {error}"
            )

    def _operation_config(
        self,
        operation_type: AIOperationType,
    ) -> GeminiOperationConfig:
        if operation_type == AIOperationType.CLIP_ANALYSIS:
            return self.config.clip_analysis

        if operation_type == AIOperationType.PROJECT_CREATIVE:
            return self.config.project_creative

        if operation_type == AIOperationType.FINAL_VIDEO_REVIEW:
            return self.config.final_video_review

        raise ValueError(
            "Unsupported Gemini operation type: "
            f"{operation_type.value}"
        )

    def _ensure_enabled(self) -> None:
        if not self.config.enabled:
            raise AIAnalysisProviderError(
                "Gemini is disabled in config/gemini.json."
            )

    def _get_api_key(self) -> str:
        environment_variable = (
            self.config
            .api_key_environment_variable
            .strip()
            or "GEMINI_API_KEY"
        )

        api_key = os.getenv(
            environment_variable
        )

        if not api_key:
            raise AIAnalysisProviderError(
                "Gemini API key environment variable "
                f"'{environment_variable}' is not set."
            )

        return api_key

    def _resolved_job_id(
        self,
        fallback_job_id: str,
    ) -> str:
        if self.job_id:
            return self.job_id

        return fallback_job_id.strip()

    def _extract_duration(
        self,
        request: FinalVideoReviewRequest,
    ) -> float:
        for attribute_name in (
            "media_info",
            "rendered_media_info",
        ):
            media_info = getattr(
                request,
                attribute_name,
                None,
            )

            if media_info is not None:
                duration = self._safe_float(
                    getattr(
                        media_info,
                        "duration_seconds",
                        0.0,
                    )
                )

                if duration > 0:
                    return duration

        return self._safe_float(
            getattr(
                request,
                "expected_duration_seconds",
                0.0,
            )
        )

    def _extract_has_audio(
        self,
        request: FinalVideoReviewRequest,
    ) -> bool:
        for attribute_name in (
            "media_info",
            "rendered_media_info",
        ):
            media_info = getattr(
                request,
                attribute_name,
                None,
            )

            if media_info is not None and hasattr(
                media_info,
                "has_audio",
            ):
                return bool(
                    getattr(
                        media_info,
                        "has_audio",
                    )
                )

        checks = getattr(
            request,
            "deterministic_checks",
            None,
        )

        if isinstance(checks, dict):
            return bool(
                checks.get(
                    "has_audio",
                    True,
                )
            )

        if checks is not None and hasattr(
            checks,
            "has_audio",
        ):
            return bool(
                getattr(
                    checks,
                    "has_audio",
                )
            )

        return True

    def _file_state_name(
        self,
        state: Any,
    ) -> str:
        if state is None:
            return ""

        raw_value = getattr(
            state,
            "value",
            None,
        )

        if raw_value is None:
            raw_value = getattr(
                state,
                "name",
                state,
            )

        normalized = str(
            raw_value
        ).strip().upper()

        if "." in normalized:
            normalized = normalized.rsplit(
                ".",
                maxsplit=1,
            )[-1]

        return normalized

    def _safe_float(
        self,
        value: Any,
    ) -> float:
        try:
            return max(
                0.0,
                float(value),
            )
        except (TypeError, ValueError):
            return 0.0

    def _log_lines(
        self,
        lines: list[str],
    ) -> None:
        for line in lines:
            self._log(line)

    def _log(
        self,
        message: str,
    ) -> None:
        if self.log_callback is not None:
            self.log_callback(message)