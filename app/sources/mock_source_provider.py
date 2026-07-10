from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.sources.source_models import (
    MediaKind,
    RightsStatus,
    SourceCandidate,
    SourceCandidateBatch,
    SourcePlatform,
    SourceProfile,
)
from app.sources.source_provider import SourceProvider


class MockSourceProvider(SourceProvider):
    """
    Deterministic test provider.

    It simulates source discovery without contacting Reddit or another
    external platform. This allows the source-filtering workflow to be
    tested without authentication, rate limits, or network access.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    def fetch_candidates(
        self,
        profile: SourceProfile,
    ) -> SourceCandidateBatch:
        discovered_candidates = self._create_mock_candidates(profile)

        accepted_candidates: list[SourceCandidate] = []

        for candidate in discovered_candidates:
            if self._matches_profile(candidate, profile):
                accepted_candidates.append(candidate)

            if len(accepted_candidates) >= profile.candidate_limit:
                break

        filtered_count = len(discovered_candidates) - len(accepted_candidates)

        return SourceCandidateBatch(
            source_profile=profile,
            candidates=accepted_candidates,
            scanned_count=len(discovered_candidates),
            filtered_count=filtered_count,
            warnings=[
                "Mock source provider is active. No external source was contacted."
            ],
        )

    def _matches_profile(
        self,
        candidate: SourceCandidate,
        profile: SourceProfile,
    ) -> bool:
        if candidate.score < profile.min_score:
            return False

        if candidate.comment_count < profile.min_comment_count:
            return False

        if candidate.is_nsfw and not profile.allow_nsfw:
            return False

        if candidate.is_crosspost and not profile.allow_crossposts:
            return False

        if profile.require_video:
            allowed_media_kinds = {MediaKind.VIDEO}

            if profile.allow_gifs:
                allowed_media_kinds.add(MediaKind.GIF)

            if candidate.media_kind not in allowed_media_kinds:
                return False

        normalized_flair = candidate.flair.strip().lower()

        allowed_flairs = {
            flair.strip().lower()
            for flair in profile.allowed_flairs
            if flair.strip()
        }

        blocked_flairs = {
            flair.strip().lower()
            for flair in profile.blocked_flairs
            if flair.strip()
        }

        if allowed_flairs and normalized_flair not in allowed_flairs:
            return False

        if normalized_flair in blocked_flairs:
            return False

        if (
            profile.max_post_age_hours is not None
            and candidate.created_utc is not None
        ):
            now = datetime.now(timezone.utc)
            age = now - candidate.created_utc

            if age.total_seconds() > profile.max_post_age_hours * 3600:
                return False

        return True

    def _create_mock_candidates(
        self,
        profile: SourceProfile,
    ) -> list[SourceCandidate]:
        now = datetime.now(timezone.utc)
        theme = profile.theme_hint.strip() or profile.community

        candidate_specs = [
            {
                "title": f"{theme}: the perfect reaction",
                "score": 3420,
                "comments": 186,
                "flair": "Video",
                "kind": MediaKind.VIDEO,
                "nsfw": False,
                "crosspost": False,
                "age_hours": 2,
            },
            {
                "title": f"{theme}: zero thoughts, just chaos",
                "score": 2890,
                "comments": 141,
                "flair": "OC",
                "kind": MediaKind.VIDEO,
                "nsfw": False,
                "crosspost": False,
                "age_hours": 5,
            },
            {
                "title": f"{theme}: instant regret",
                "score": 2150,
                "comments": 93,
                "flair": "Video",
                "kind": MediaKind.VIDEO,
                "nsfw": False,
                "crosspost": True,
                "age_hours": 10,
            },
            {
                "title": f"{theme}: unexpected ending",
                "score": 1740,
                "comments": 72,
                "flair": "GIF",
                "kind": MediaKind.GIF,
                "nsfw": False,
                "crosspost": False,
                "age_hours": 18,
            },
            {
                "title": f"{theme}: low-score test candidate",
                "score": 12,
                "comments": 1,
                "flair": "Video",
                "kind": MediaKind.VIDEO,
                "nsfw": False,
                "crosspost": False,
                "age_hours": 1,
            },
            {
                "title": f"{theme}: filtered NSFW test candidate",
                "score": 4100,
                "comments": 230,
                "flair": "Video",
                "kind": MediaKind.VIDEO,
                "nsfw": True,
                "crosspost": False,
                "age_hours": 3,
            },
        ]

        candidates: list[SourceCandidate] = []

        for index, spec in enumerate(candidate_specs, start=1):
            external_post_id = f"mock_{index:03d}"

            candidates.append(
                SourceCandidate(
                    candidate_id=(
                        f"{profile.id}_{external_post_id}"
                    ),
                    source_profile_id=profile.id,
                    platform=SourcePlatform.REDDIT,
                    community=profile.community,
                    external_post_id=external_post_id,
                    title=str(spec["title"]),
                    post_url=(
                        f"https://example.invalid/r/{profile.community}/"
                        f"{external_post_id}"
                    ),
                    media_url=f"mock://media/{external_post_id}.mp4",
                    media_kind=spec["kind"],
                    author_name=f"mock_user_{index:02d}",
                    created_utc=now - timedelta(
                        hours=float(spec["age_hours"])
                    ),
                    score=int(spec["score"]),
                    comment_count=int(spec["comments"]),
                    flair=str(spec["flair"]),
                    is_nsfw=bool(spec["nsfw"]),
                    is_crosspost=bool(spec["crosspost"]),
                    rights_status=RightsStatus.UNKNOWN,
                    metadata={
                        "mock": True,
                        "provider": self.provider_name,
                    },
                )
            )

        return candidates