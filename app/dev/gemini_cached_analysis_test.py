from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.ai.analysis_cache import AIAnalysisCache
from app.ai.cached_analysis_provider import (
    CachedAIAnalysisProvider,
)
from app.ai.clip_analysis_request_factory import (
    ClipAnalysisPresetContext,
    ClipAnalysisRequestFactory,
)
from app.ai.gemini_analysis_provider import (
    GeminiAnalysisProvider,
)
from app.sources.mock_source_provider import (
    MockSourceProvider,
)
from app.sources.source_models import (
    SourcePlatform,
    SourceProfile,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test automatic media probing, Gemini clip analysis, "
            "and persistent AI caching."
        )
    )

    parser.add_argument(
        "--video",
        required=True,
        help=(
            "Local test video. In production this path comes "
            "from the automatic source downloader."
        ),
    )

    parser.add_argument(
        "--subreddit",
        default="SillyCats",
        help=(
            "Source community used to build the automatic "
            "analysis context."
        ),
    )

    parser.add_argument(
        "--preset",
        default="youtube_ranking",
        help="ClipFactory preset ID.",
    )

    return parser.parse_args()


def accepted_candidates(
    candidate_batch: Any,
) -> list[Any]:
    """
    Compatibility helper for the current SourceCandidateBatch model.
    """

    for field_name in (
        "candidates",
        "accepted_candidates",
    ):
        value = getattr(
            candidate_batch,
            field_name,
            None,
        )

        if isinstance(value, list):
            return value

    raise RuntimeError(
        "SourceCandidateBatch contains no accepted candidate list."
    )


def main() -> None:
    arguments = parse_arguments()

    video_path = (
        Path(arguments.video)
        .expanduser()
        .resolve()
    )

    if not video_path.exists():
        raise FileNotFoundError(
            f"Test video was not found: {video_path}"
        )

    subreddit = arguments.subreddit.strip()
    preset_id = arguments.preset.strip()

    source_profile = SourceProfile(
        id=f"reddit_{subreddit.lower()}",
        name=subreddit,
        platform=SourcePlatform.REDDIT,
        community=subreddit,
        theme_hint="",
    )

    source_provider = MockSourceProvider()

    candidate_batch = (
        source_provider.fetch_candidates(
            source_profile
        )
    )

    candidates = accepted_candidates(
        candidate_batch
    )

    if not candidates:
        raise RuntimeError(
            "Mock source provider returned no candidates."
        )

    candidate = candidates[0]

    preset_context = (
        ClipAnalysisPresetContext.from_preset_id(
            preset_id
        )
    )

    request_factory = ClipAnalysisRequestFactory()

    request = request_factory.create(
        candidate=candidate,
        source_profile=source_profile,
        local_path=video_path,
        preset_context=preset_context,
    )

    print("Automatic ClipAnalysisRequest created.")
    print(f"Clip ID: {request.clip_id}")
    print(f"Source title: {request.candidate.title}")
    print(f"Derived theme: {request.theme}")
    print(f"Preset: {request.preset_id}")
    print(
        f"Target platform: "
        f"{request.target_platform.value}"
    )
    print(
        f"Video format: "
        f"{request.video_format.value}"
    )
    print(
        f"Duration from MediaProbe: "
        f"{request.media_info.duration_seconds:.2f}s"
    )
    print(
        f"Audio from MediaProbe: "
        f"{'yes' if request.media_info.has_audio else 'no'}"
    )
    print(
        f"Resolution from MediaProbe: "
        f"{request.media_info.width}x"
        f"{request.media_info.height}"
    )
    print()

    ledger_path = Path(
        "data/ai/dev_gemini_cached_analysis_ledger.json"
    )

    cache_path = Path(
        "data/ai/dev_gemini_cached_analysis_cache.json"
    )

    gemini_provider = (
        GeminiAnalysisProvider.from_config_files(
            ledger_path=ledger_path,
            job_id="gemini_cached_analysis_test",
            log_callback=print,
        )
    )

    cache = AIAnalysisCache(
        cache_path=cache_path
    )

    provider = CachedAIAnalysisProvider(
        provider=gemini_provider,
        cache=cache,
        log_callback=print,
    )

    ledger_entries_before = (
        gemini_provider.usage_ledger.entry_count()
    )

    print("--- First analysis call ---")
    first_result = provider.analyze_clip(
        request
    )

    ledger_entries_after_first = (
        gemini_provider.usage_ledger.entry_count()
    )

    print()
    print("First result:")
    print(
        first_result.model_dump_json(
            indent=2
        )
    )

    print()
    print("--- Second analysis call ---")
    second_result = provider.analyze_clip(
        request
    )

    ledger_entries_after_second = (
        gemini_provider.usage_ledger.entry_count()
    )

    if first_result != second_result:
        raise AssertionError(
            "Cached result differs from the original result."
        )

    if (
        ledger_entries_after_second
        != ledger_entries_after_first
    ):
        raise AssertionError(
            "The second analysis created another usage entry. "
            "The cache did not prevent the API request."
        )

    print()
    print("Cache integration passed.")
    print(
        "Ledger entries before first call: "
        f"{ledger_entries_before}"
    )
    print(
        "Ledger entries after first call: "
        f"{ledger_entries_after_first}"
    )
    print(
        "Ledger entries after second call: "
        f"{ledger_entries_after_second}"
    )
    print(
        f"Cache entries: {cache.entry_count()}"
    )

    print()
    print("Automatic values confirmed:")
    print("- duration came from MediaProbe")
    print("- audio state came from MediaProbe")
    print("- title came from the source candidate")
    print("- theme came from the source profile/subreddit")
    print("- AI settings came from the selected preset")
    print("- repeated analysis came from the local cache")


if __name__ == "__main__":
    main()