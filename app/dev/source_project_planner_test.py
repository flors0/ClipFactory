from __future__ import annotations

import argparse
from typing import Any

from app.ai.clip_analysis_request_factory import (
    ClipAnalysisPresetContext,
)
from app.planning.source_project_planner import (
    SourceProjectPlanner,
)
from app.sources.mock_source_provider import (
    MockSourceProvider,
)
from app.sources.source_profile_factory import (
    SourceProfileFactory,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a source project plan from only a "
            "subreddit and preset."
        )
    )

    parser.add_argument(
        "--subreddit",
        default="SillyCats",
        help="Subreddit name, r/name, or Reddit URL.",
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
        "SourceCandidateBatch contains no accepted "
        "candidate list."
    )


def main() -> None:
    arguments = parse_arguments()

    profile_factory = SourceProfileFactory()

    source_profile = (
        profile_factory.create_reddit_profile(
            arguments.subreddit
        )
    )

    preset_context = (
        ClipAnalysisPresetContext.from_preset_id(
            arguments.preset
        )
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

    planner = SourceProjectPlanner()

    plan = planner.create_plan(
        source_profile=source_profile,
        candidates=candidates,
        preset_context=preset_context,
    )

    print("Minimal user input:")
    print(f"Subreddit: {arguments.subreddit}")
    print(f"Preset: {arguments.preset}")
    print()

    for line in plan.to_log_lines():
        print(line)

    print()
    print("Full project plan:")
    print(plan.model_dump_json(indent=2))

    if not plan.theme:
        raise AssertionError(
            "Planner created an empty theme."
        )

    if plan.candidate_count != len(candidates):
        raise AssertionError(
            "Project plan candidate count is incorrect."
        )

    if plan.preset_id != arguments.preset.strip():
        raise AssertionError(
            "Project plan did not preserve the preset ID."
        )

    print()
    print("Source project planning passed.")
    print("No API request was made.")
    print()
    print("Only subreddit and preset were user inputs.")


if __name__ == "__main__":
    main()