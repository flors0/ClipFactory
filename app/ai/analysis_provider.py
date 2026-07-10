from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.analysis_models import (
    ClipAnalysisRequest,
    ClipAnalysisResult,
    FinalVideoReviewRequest,
    FinalVideoReviewResult,
    ProjectCreativeRequest,
    ProjectCreativeResult,
)


class AIAnalysisProviderError(Exception):
    pass


class AIAnalysisProvider(ABC):
    """
    Provider-independent interface for creative video analysis.

    Gemini, Twelve Labs, or another provider can implement this interface
    without changing the rest of ClipFactory.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    def cache_identity(self) -> str:
        """
        Identifies the provider configuration used for cached results.

        Real providers should include the model and prompt/schema version,
        for example:

            gemini:gemini-2.5-flash:clip-analysis-v1
            twelve-labs:marengo-2.7:clip-analysis-v1

        If the model or prompt changes, the identity should change as well.
        This prevents old cached results from being reused incorrectly.
        """

        return self.provider_name

    @abstractmethod
    def analyze_clip(
        self,
        request: ClipAnalysisRequest,
    ) -> ClipAnalysisResult:
        """
        Analyze one downloaded clip and determine whether it fits the
        requested theme and format.
        """

        raise NotImplementedError

    @abstractmethod
    def create_project_copy(
        self,
        request: ProjectCreativeRequest,
    ) -> ProjectCreativeResult:
        """
        Generate content fields such as the header and ranking captions.

        This method must not change locked preset styling.
        """

        raise NotImplementedError

    @abstractmethod
    def review_final_video(
        self,
        request: FinalVideoReviewRequest,
    ) -> FinalVideoReviewResult:
        """
        Review the fully rendered video after deterministic Python checks
        have already completed.
        """

        raise NotImplementedError