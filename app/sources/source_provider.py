from __future__ import annotations

from abc import ABC, abstractmethod

from app.sources.source_models import SourceCandidateBatch, SourceProfile


class SourceProviderError(Exception):
    pass


class SourceProvider(ABC):
    """
    Abstract source-discovery interface.

    ClipFactory should not depend directly on Reddit. It should depend on
    this interface so other sources can be added later without changing
    the analysis and rendering pipeline.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def fetch_candidates(
        self,
        profile: SourceProfile,
    ) -> SourceCandidateBatch:
        """
        Fetch candidate posts or clips matching a source profile.

        Implementations are responsible for:
        - requesting source data
        - converting results to SourceCandidate objects
        - applying cheap metadata filters
        - respecting API limits and authentication requirements

        This method should not perform AI video analysis.
        """

        raise NotImplementedError