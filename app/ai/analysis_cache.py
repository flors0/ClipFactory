from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.analysis_models import (
    ClipAnalysisRequest,
    ClipAnalysisResult,
    FinalVideoReviewRequest,
    FinalVideoReviewResult,
    ProjectCreativeRequest,
    ProjectCreativeResult,
)


ResultModel = TypeVar("ResultModel", bound=BaseModel)


class AIAnalysisCache:
    """
    Persistent cache for AI results.

    A cache key includes:
    - analysis type
    - provider/model/prompt identity
    - relevant request settings
    - local media file fingerprint

    Changing the AI model, prompt version, theme, platform, permissions,
    media file, or other relevant inputs creates a different cache key.
    """

    CACHE_VERSION = 1

    def __init__(
        self,
        cache_path: Path = Path("data/ai/analysis_cache.json"),
    ) -> None:
        self.cache_path = cache_path
        self._data = self._load()

    def get_clip_analysis(
        self,
        provider_identity: str,
        request: ClipAnalysisRequest,
    ) -> ClipAnalysisResult | None:
        return self._get_result(
            namespace="clip_analysis",
            provider_identity=provider_identity,
            request_payload=self._clip_request_payload(request),
            result_model=ClipAnalysisResult,
        )

    def save_clip_analysis(
        self,
        provider_identity: str,
        request: ClipAnalysisRequest,
        result: ClipAnalysisResult,
    ) -> None:
        self._save_result(
            namespace="clip_analysis",
            provider_identity=provider_identity,
            request_payload=self._clip_request_payload(request),
            result=result,
        )

    def get_project_creative(
        self,
        provider_identity: str,
        request: ProjectCreativeRequest,
    ) -> ProjectCreativeResult | None:
        return self._get_result(
            namespace="project_creative",
            provider_identity=provider_identity,
            request_payload=self._project_creative_payload(request),
            result_model=ProjectCreativeResult,
        )

    def save_project_creative(
        self,
        provider_identity: str,
        request: ProjectCreativeRequest,
        result: ProjectCreativeResult,
    ) -> None:
        self._save_result(
            namespace="project_creative",
            provider_identity=provider_identity,
            request_payload=self._project_creative_payload(request),
            result=result,
        )

    def get_final_video_review(
        self,
        provider_identity: str,
        request: FinalVideoReviewRequest,
    ) -> FinalVideoReviewResult | None:
        return self._get_result(
            namespace="final_video_review",
            provider_identity=provider_identity,
            request_payload=self._final_review_payload(request),
            result_model=FinalVideoReviewResult,
        )

    def save_final_video_review(
        self,
        provider_identity: str,
        request: FinalVideoReviewRequest,
        result: FinalVideoReviewResult,
    ) -> None:
        self._save_result(
            namespace="final_video_review",
            provider_identity=provider_identity,
            request_payload=self._final_review_payload(request),
            result=result,
        )

    def entry_count(self) -> int:
        entries = self._data.get("entries", {})
        return len(entries)

    def clear(self) -> None:
        self._data = self._empty_cache()
        self._save()

    def _get_result(
        self,
        namespace: str,
        provider_identity: str,
        request_payload: dict[str, Any],
        result_model: type[ResultModel],
    ) -> ResultModel | None:
        cache_key = self._build_cache_key(
            namespace=namespace,
            provider_identity=provider_identity,
            request_payload=request_payload,
        )

        entries = self._data.get("entries", {})
        entry = entries.get(cache_key)

        if not isinstance(entry, dict):
            return None

        result_data = entry.get("result")

        if not isinstance(result_data, dict):
            return None

        try:
            return result_model.model_validate(result_data)
        except Exception:
            return None

    def _save_result(
        self,
        namespace: str,
        provider_identity: str,
        request_payload: dict[str, Any],
        result: BaseModel,
    ) -> None:
        cache_key = self._build_cache_key(
            namespace=namespace,
            provider_identity=provider_identity,
            request_payload=request_payload,
        )

        entries = self._data.setdefault("entries", {})

        entries[cache_key] = {
            "namespace": namespace,
            "provider_identity": provider_identity,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "request_fingerprint": cache_key,
            "result": result.model_dump(mode="json"),
        }

        self._save()

    def _build_cache_key(
        self,
        namespace: str,
        provider_identity: str,
        request_payload: dict[str, Any],
    ) -> str:
        key_payload = {
            "cache_version": self.CACHE_VERSION,
            "namespace": namespace,
            "provider_identity": provider_identity,
            "request": request_payload,
        }

        serialized = json.dumps(
            key_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _clip_request_payload(
        self,
        request: ClipAnalysisRequest,
    ) -> dict[str, Any]:
        candidate = request.candidate
        media = request.media_info

        return {
            "clip_id": request.clip_id,
            "local_media_fingerprint": self._file_fingerprint(
                request.local_path
            ),
            "candidate": {
                "candidate_id": candidate.candidate_id,
                "external_post_id": candidate.external_post_id,
                "community": candidate.community,
                "title": candidate.title,
                "media_url": candidate.media_url,
                "media_kind": candidate.media_kind.value,
                "flair": candidate.flair,
                "is_nsfw": candidate.is_nsfw,
            },
            "media_info": {
                "duration_seconds": media.duration_seconds,
                "width": media.width,
                "height": media.height,
                "fps": media.fps,
                "has_video": media.has_video,
                "has_audio": media.has_audio,
                "video_codec": media.video_codec,
                "audio_codec": media.audio_codec,
            },
            "preset_id": request.preset_id,
            "target_platform": request.target_platform.value,
            "video_format": request.video_format.value,
            "theme": request.theme,
            "desired_caption_style": request.desired_caption_style,
            "permissions": request.permissions.model_dump(mode="json"),
        }

    def _project_creative_payload(
        self,
        request: ProjectCreativeRequest,
    ) -> dict[str, Any]:
        return request.model_dump(mode="json")

    def _final_review_payload(
        self,
        request: FinalVideoReviewRequest,
    ) -> dict[str, Any]:
        payload = request.model_dump(mode="json")

        payload["rendered_media_fingerprint"] = self._file_fingerprint(
            request.video_path
        )

        return payload

    def _file_fingerprint(self, path: Path) -> dict[str, Any]:
        expanded_path = path.expanduser()

        if not expanded_path.exists():
            return {
                "exists": False,
                "path": expanded_path.as_posix(),
            }

        resolved_path = expanded_path.resolve()
        stat = resolved_path.stat()

        return {
            "exists": True,
            "path": resolved_path.as_posix(),
            "size_bytes": stat.st_size,
            "modified_time_ns": stat.st_mtime_ns,
        }

    def _load(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return self._empty_cache()

        try:
            raw_data = json.loads(
                self.cache_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return self._empty_cache()

        if not isinstance(raw_data, dict):
            return self._empty_cache()

        if raw_data.get("cache_version") != self.CACHE_VERSION:
            return self._empty_cache()

        if not isinstance(raw_data.get("entries"), dict):
            raw_data["entries"] = {}

        return raw_data

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self.cache_path.with_suffix(
            self.cache_path.suffix + ".tmp"
        )

        temp_path.write_text(
            json.dumps(
                self._data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temp_path.replace(self.cache_path)

    def _empty_cache(self) -> dict[str, Any]:
        return {
            "cache_version": self.CACHE_VERSION,
            "entries": {},
        }