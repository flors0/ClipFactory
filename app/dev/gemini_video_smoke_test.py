from __future__ import annotations

import argparse
from pathlib import Path

from app.ai.analysis_models import ClipAnalysisResult
from app.ai.gemini_analysis_provider import GeminiAnalysisProvider


MAX_TEST_DURATION_SECONDS = 30.0
MAX_TEST_FILE_SIZE_BYTES = 100 * 1024 * 1024


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one controlled Gemini video-analysis request "
            "through ClipFactory's real provider."
        )
    )

    parser.add_argument(
        "--video",
        required=True,
        help="Path to the local test video.",
    )

    parser.add_argument(
        "--duration",
        required=True,
        type=float,
        help="Approximate video duration in seconds.",
    )

    parser.add_argument(
        "--theme",
        default="funny animal clips",
        help="Theme against which Gemini should evaluate the clip.",
    )

    parser.add_argument(
        "--title",
        default="Local Gemini video test",
        help="Optional source-title context for the analysis.",
    )

    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Use this flag when the video contains no audio stream.",
    )

    return parser.parse_args()


def validate_test_video(
    video_path: Path,
    duration_seconds: float,
) -> None:
    if not video_path.exists():
        raise FileNotFoundError(
            f"Test video was not found: {video_path}"
        )

    if not video_path.is_file():
        raise ValueError(
            f"Test video path is not a file: {video_path}"
        )

    if duration_seconds <= 0:
        raise ValueError(
            "Video duration must be greater than zero."
        )

    if duration_seconds > MAX_TEST_DURATION_SECONDS:
        raise ValueError(
            "The first Gemini video test is limited to "
            f"{MAX_TEST_DURATION_SECONDS:.0f} seconds. "
            f"Provided duration: {duration_seconds:.2f} seconds."
        )

    file_size = video_path.stat().st_size

    if file_size > MAX_TEST_FILE_SIZE_BYTES:
        raise ValueError(
            "The first Gemini video test is limited to 100 MB. "
            f"Provided file size: "
            f"{file_size / 1024 / 1024:.2f} MB."
        )


def build_analysis_payload(
    video_path: Path,
    duration_seconds: float,
    theme: str,
    title: str,
    has_audio: bool,
) -> dict:
    """
    Build prompt context without constructing the complete source pipeline.

    This smoke test deliberately exercises the real Gemini upload,
    structured-output, budget, usage, and cleanup flow before we connect
    the provider to real SourceCandidate objects.
    """

    clip_id = f"local_test_{video_path.stem}"

    return {
        "clip_id": clip_id,
        "theme": theme,
        "preset_id": "youtube_ranking",
        "target_platform": "youtube_shorts",
        "video_format": "ranking",
        "desired_caption_style": "short lowercase reaction",
        "candidate": {
            "candidate_id": clip_id,
            "external_post_id": "local_video_smoke_test",
            "community": "local_test",
            "title": title,
            "media_kind": "video",
            "rights_status": "unknown",
        },
        "media_info": {
            "duration_seconds": duration_seconds,
            "has_video": True,
            "has_audio": has_audio,
        },
        "permissions": {
            "allow_header_text": True,
            "allow_ranking_captions": True,
            "allow_clip_reordering": False,
            "allow_trim_suggestions": True,
            "allow_transition_selection": False,
            "allow_style_changes": False,
            "allow_duration_rule_changes": False,
        },
    }


def main() -> None:
    arguments = parse_arguments()

    video_path = Path(arguments.video).expanduser().resolve()
    duration_seconds = float(arguments.duration)
    has_audio = not arguments.no_audio

    validate_test_video(
        video_path=video_path,
        duration_seconds=duration_seconds,
    )

    print("Gemini video smoke test")
    print(f"Video: {video_path.name}")
    print(
        "File size: "
        f"{video_path.stat().st_size / 1024 / 1024:.2f} MB"
    )
    print(f"Estimated duration: {duration_seconds:.2f}s")
    print(f"Audio expected: {'yes' if has_audio else 'no'}")
    print(f"Theme: {arguments.theme}")
    print()

    provider = GeminiAnalysisProvider.from_config_files(
        ledger_path=Path(
            "data/ai/dev_gemini_video_ledger.json"
        ),
        job_id="gemini_video_smoke_test",
        log_callback=print,
    )

    payload = build_analysis_payload(
        video_path=video_path,
        duration_seconds=duration_seconds,
        theme=arguments.theme,
        title=arguments.title,
        has_audio=has_audio,
    )

    prompt = (
        provider
        .prompt_builder
        .build_clip_analysis_from_payload(payload)
    )

    print("Starting one real Gemini video-analysis request.")
    print()

    # This deliberately calls the provider's shared internal execution
    # pipeline. The next integration step will invoke it through the
    # public analyze_clip() provider contract.
    result = provider._run_operation(
        prompt=prompt,
        result_model=ClipAnalysisResult,
        request_label=(
            f"video_smoke_test:{video_path.stem}"
        ),
        fallback_job_id="gemini_video_smoke_test",
        media_path=video_path,
        video_seconds=duration_seconds,
        audio_seconds=(
            duration_seconds
            if has_audio
            else 0.0
        ),
        has_video=True,
        has_audio=has_audio,
    )

    print()
    print("Validated ClipAnalysisResult:")
    print(result.model_dump_json(indent=2))

    print()
    print("Recorded job usage:")

    summary = provider.usage_ledger.summary_for_job(
        "gemini_video_smoke_test"
    )

    for line in summary.to_log_lines(
        "Gemini video smoke-test usage"
    ):
        print(line)

    print()
    print("Video smoke test completed successfully.")
    print(
        "Confirm that the log above contains: "
        "'Uploaded Gemini file was deleted.'"
    )


if __name__ == "__main__":
    main()