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

    A future Gemini provider will implement this interface. ClipFactory
    itself does not need to know which AI service is being used.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

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