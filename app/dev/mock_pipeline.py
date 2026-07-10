from __future__ import annotations

from pathlib import Path

from app.ai.analysis_models import (
    ClipAnalysisRequest,
    ProjectCreativeRequest,
    TargetPlatform,
    VideoFormat,
)
from app.ai.mock_analysis_provider import MockAIAnalysisProvider
from app.analyze.analysis_models import MediaInfo
from app.sources.mock_source_provider import MockSourceProvider
from app.sources.source_models import (
    SourceProfile,
    SourceSort,
    SourceTimeFilter,
)


def main() -> None:
    source_profile = SourceProfile(
        id="reddit_silly_cats",
        name="Silly Cats",
        community="SillyCats",
        theme_hint="silly cats",
        sort=SourceSort.TOP,
        time_filter=SourceTimeFilter.WEEK,
        candidate_limit=10,
        min_score=100,
        min_comment_count=10,
        require_video=True,
        allow_gifs=True,
        allow_nsfw=False,
        allow_crossposts=True,
    )

    source_provider = MockSourceProvider()
    ai_provider = MockAIAnalysisProvider()

    candidate_batch = source_provider.fetch_candidates(source_profile)

    for line in candidate_batch.to_log_lines():
        print(line)

    clip_analyses = []

    for index, candidate in enumerate(
        candidate_batch.candidates,
        start=1,
    ):
        mock_path = Path(
            f"data/mock/{candidate.candidate_id}.mp4"
        )

        media_info = MediaInfo(
            path=mock_path,
            exists=True,
            duration_seconds=5.0 + index,
            width=1080,
            height=1920,
            fps=30.0,
            has_video=True,
            has_audio=index % 2 == 0,
            video_codec="h264",
            audio_codec="aac" if index % 2 == 0 else "",
        )

        request = ClipAnalysisRequest(
            clip_id=candidate.candidate_id,
            local_path=mock_path,
            candidate=candidate,
            media_info=media_info,
            preset_id="youtube_ranking",
            target_platform=TargetPlatform.YOUTUBE_SHORTS,
            video_format=VideoFormat.RANKING,
            theme=source_profile.theme_hint,
            desired_caption_style="short, funny, lowercase",
        )

        analysis = ai_provider.analyze_clip(request)
        clip_analyses.append(analysis)

        print()
        print(f"Clip analysis: {analysis.clip_id}")
        print(analysis.model_dump_json(indent=2))

    creative_request = ProjectCreativeRequest(
        project_name="silly_cats_test",
        preset_id="youtube_ranking",
        target_platform=TargetPlatform.YOUTUBE_SHORTS,
        video_format=VideoFormat.RANKING,
        source_profile_id=source_profile.id,
        community=source_profile.community,
        theme=source_profile.theme_hint,
        target_duration_seconds=65.0,
        min_duration_seconds=60.0,
        max_duration_seconds=90.0,
        clip_analyses=clip_analyses,
    )

    creative_result = ai_provider.create_project_copy(
        creative_request
    )

    print()
    print("Project creative result:")
    print(creative_result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()