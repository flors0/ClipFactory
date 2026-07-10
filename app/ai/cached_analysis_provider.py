from __future__ import annotations

from collections.abc import Callable

from app.ai.analysis_cache import AIAnalysisCache
from app.ai.analysis_models import (
    ClipAnalysisRequest,
    ClipAnalysisResult,
    FinalVideoReviewRequest,
    FinalVideoReviewResult,
    ProjectCreativeRequest,
    ProjectCreativeResult,
)
from app.ai.analysis_provider import AIAnalysisProvider


class CachedAIAnalysisProvider(AIAnalysisProvider):
    """
    Provider decorator that adds persistent caching to any AI provider.

    The wrapped provider can be Gemini, Twelve Labs, a mock provider,
    or another implementation.
    """

    def __init__(
        self,
        provider: AIAnalysisProvider,
        cache: AIAnalysisCache | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache or AIAnalysisCache()
        self.log_callback = log_callback

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @property
    def cache_identity(self) -> str:
        return self.provider.cache_identity

    def analyze_clip(
        self,
        request: ClipAnalysisRequest,
    ) -> ClipAnalysisResult:
        cached_result = self.cache.get_clip_analysis(
            provider_identity=self.cache_identity,
            request=request,
        )

        if cached_result is not None:
            self._log(f"AI cache hit: clip analysis {request.clip_id}")
            return cached_result

        self._log(f"AI cache miss: clip analysis {request.clip_id}")

        result = self.provider.analyze_clip(request)

        self.cache.save_clip_analysis(
            provider_identity=self.cache_identity,
            request=request,
            result=result,
        )

        self._log(f"AI result cached: clip analysis {request.clip_id}")
        return result

    def create_project_copy(
        self,
        request: ProjectCreativeRequest,
    ) -> ProjectCreativeResult:
        cached_result = self.cache.get_project_creative(
            provider_identity=self.cache_identity,
            request=request,
        )

        if cached_result is not None:
            self._log(
                f"AI cache hit: project creative {request.project_name}"
            )
            return cached_result

        self._log(
            f"AI cache miss: project creative {request.project_name}"
        )

        result = self.provider.create_project_copy(request)

        self.cache.save_project_creative(
            provider_identity=self.cache_identity,
            request=request,
            result=result,
        )

        self._log(
            f"AI result cached: project creative {request.project_name}"
        )
        return result

    def review_final_video(
        self,
        request: FinalVideoReviewRequest,
    ) -> FinalVideoReviewResult:
        cached_result = self.cache.get_final_video_review(
            provider_identity=self.cache_identity,
            request=request,
        )

        if cached_result is not None:
            self._log(
                f"AI cache hit: final review {request.project_name}"
            )
            return cached_result

        self._log(
            f"AI cache miss: final review {request.project_name}"
        )

        result = self.provider.review_final_video(request)

        self.cache.save_final_video_review(
            provider_identity=self.cache_identity,
            request=request,
            result=result,
        )

        self._log(
            f"AI result cached: final review {request.project_name}"
        )
        return result

    def _log(self, message: str) -> None:
        if self.log_callback is not None:
            self.log_callback(message)