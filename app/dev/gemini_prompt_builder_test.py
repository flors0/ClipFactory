from __future__ import annotations

from app.ai.gemini_config import load_gemini_config
from app.ai.gemini_prompt_builder import (
    GeminiPromptBuilder,
    GeminiPromptPackage,
)


def print_prompt_summary(
    title: str,
    prompt: GeminiPromptPackage,
) -> None:
    print()
    print(f"--- {title} ---")
    print(f"Operation: {prompt.operation_type.value}")
    print(f"Prompt version: {prompt.prompt_version}")
    print(f"Characters: {len(prompt.text):,}")
    print()
    print(prompt.text)


def assert_private_values_removed(
    prompt: GeminiPromptPackage,
) -> None:
    forbidden_values = [
        r"C:\Users\flori\private\clip.mp4",
        r"C:\Users\flori\private\final.mp4",
        "SECRET_API_KEY_VALUE",
    ]

    for forbidden_value in forbidden_values:
        if forbidden_value in prompt.text:
            raise AssertionError(
                "Private value was included in Gemini prompt: "
                f"{forbidden_value}"
            )


def main() -> None:
    config = load_gemini_config()
    builder = GeminiPromptBuilder(config)

    clip_payload = {
        "clip_id": "reddit_silly_cats_mock_001",
        "local_path": r"C:\Users\flori\private\clip.mp4",
        "theme": "silly cats",
        "preset_id": "youtube_ranking",
        "target_platform": "youtube_shorts",
        "video_format": "ranking",
        "desired_caption_style": "short lowercase reaction",
        "candidate": {
            "title": "Cat realizes the box is moving",
            "community": "SillyCats",
            "score": 4210,
            "rights_status": "unknown",
        },
        "media_info": {
            "duration_seconds": 8.5,
            "width": 1080,
            "height": 1920,
            "has_audio": True,
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
        "api_key": "SECRET_API_KEY_VALUE",
    }

    project_payload = {
        "project_name": "silly_cats_test",
        "theme": "silly cats",
        "target_platform": "youtube_shorts",
        "video_format": "ranking",
        "preset_id": "youtube_ranking",
        "clip_analyses": [
            {
                "clip_id": "reddit_silly_cats_mock_001",
                "summary": "A cat reacts to a moving box.",
                "usable": True,
                "ranking_caption": "the box fought back",
            },
            {
                "clip_id": "reddit_silly_cats_mock_002",
                "summary": "A cat misses a simple jump.",
                "usable": True,
                "ranking_caption": "confidence left the chat",
            },
        ],
        "permissions": {
            "allow_header_text": True,
            "allow_ranking_captions": True,
            "allow_clip_reordering": False,
            "allow_style_changes": False,
        },
    }

    final_review_payload = {
        "project_name": "silly_cats_test",
        "video_path": r"C:\Users\flori\private\final.mp4",
        "target_platform": "youtube_shorts",
        "video_format": "ranking",
        "expected_duration_seconds": 65.0,
        "deterministic_checks": {
            "duration_valid": True,
            "has_video": True,
            "has_audio": True,
        },
    }

    clip_prompt = (
        builder.build_clip_analysis_from_payload(
            clip_payload
        )
    )

    project_prompt = (
        builder.build_project_creative_from_payload(
            project_payload
        )
    )

    final_review_prompt = (
        builder.build_final_video_review_from_payload(
            final_review_payload
        )
    )

    assert_private_values_removed(clip_prompt)
    assert_private_values_removed(project_prompt)
    assert_private_values_removed(final_review_prompt)

    if "rights status is unknown" in clip_prompt.text.lower():
        raise AssertionError(
            "Prompt should not invent rights conclusions."
        )

    if "recommended_clip_order must be empty" not in (
        project_prompt.text
    ):
        raise AssertionError(
            "Project prompt does not preserve reorder permissions."
        )

    print("Gemini prompt privacy checks passed.")
    print("No API request was made.")

    print_prompt_summary(
        "Clip analysis prompt",
        clip_prompt,
    )

    print_prompt_summary(
        "Project creative prompt",
        project_prompt,
    )

    print_prompt_summary(
        "Final video review prompt",
        final_review_prompt,
    )


if __name__ == "__main__":
    main()