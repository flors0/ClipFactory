from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.ai.usage_models import AIUsageRecord, AIUsageSummary


class AIUsageLedger:
    """
    Persistent provider-independent usage ledger.

    All timestamps are stored in UTC. Daily and monthly summaries use the
    computer's current local timezone when grouping records.
    """

    LEDGER_VERSION = 1

    def __init__(
        self,
        ledger_path: Path = Path("data/ai/usage_ledger.json"),
    ) -> None:
        self.ledger_path = ledger_path
        self._data = self._load()

    def record_usage(
        self,
        record: AIUsageRecord,
    ) -> AIUsageRecord:
        records = self._data.setdefault("records", [])
        records.append(record.model_dump(mode="json"))

        self._save()
        return record

    def get_records(self) -> list[AIUsageRecord]:
        raw_records = self._data.get("records", [])
        records: list[AIUsageRecord] = []

        if not isinstance(raw_records, list):
            return records

        for raw_record in raw_records:
            if not isinstance(raw_record, dict):
                continue

            try:
                records.append(
                    AIUsageRecord.model_validate(raw_record)
                )
            except Exception:
                continue

        return records

    def current_day_summary(self) -> AIUsageSummary:
        current_day = datetime.now().astimezone().date()
        return self.summary_for_day(current_day)

    def current_month_summary(self) -> AIUsageSummary:
        local_now = datetime.now().astimezone()

        return self.summary_for_month(
            year=local_now.year,
            month=local_now.month,
        )

    def summary_for_day(
        self,
        target_day: date,
    ) -> AIUsageSummary:
        matching_records = [
            record
            for record in self.get_records()
            if self._local_datetime(record.created_at_utc).date()
            == target_day
        ]

        return self.summarize(matching_records)

    def summary_for_month(
        self,
        year: int,
        month: int,
    ) -> AIUsageSummary:
        matching_records: list[AIUsageRecord] = []

        for record in self.get_records():
            local_timestamp = self._local_datetime(
                record.created_at_utc
            )

            if (
                local_timestamp.year == year
                and local_timestamp.month == month
            ):
                matching_records.append(record)

        return self.summarize(matching_records)

    def summary_for_job(
        self,
        job_id: str,
    ) -> AIUsageSummary:
        normalized_job_id = job_id.strip()

        matching_records = [
            record
            for record in self.get_records()
            if record.job_id == normalized_job_id
        ]

        return self.summarize(matching_records)

    def summarize(
        self,
        records: list[AIUsageRecord],
    ) -> AIUsageSummary:
        input_tokens = sum(
            record.input_tokens
            for record in records
        )
        output_tokens = sum(
            record.output_tokens
            for record in records
        )
        cached_input_tokens = sum(
            record.cached_input_tokens
            for record in records
        )
        thinking_tokens = sum(
            record.thinking_tokens
            for record in records
        )

        estimated_cost_usd = sum(
            record.estimated_cost_usd
            for record in records
        )

        records_with_actual_cost = [
            record
            for record in records
            if record.actual_cost_usd is not None
        ]

        known_actual_cost_usd = sum(
            record.actual_cost_usd or 0.0
            for record in records_with_actual_cost
        )

        billable_cost_usd = sum(
            record.billable_cost_usd
            for record in records
        )

        return AIUsageSummary(
            records_count=len(records),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=(
                input_tokens
                + output_tokens
                + thinking_tokens
            ),
            video_seconds=sum(
                record.video_seconds
                for record in records
            ),
            audio_seconds=sum(
                record.audio_seconds
                for record in records
            ),
            estimated_cost_usd=estimated_cost_usd,
            known_actual_cost_usd=known_actual_cost_usd,
            billable_cost_usd=billable_cost_usd,
            records_with_actual_cost=len(
                records_with_actual_cost
            ),
        )

    def entry_count(self) -> int:
        return len(self.get_records())

    def clear(self) -> None:
        self._data = self._empty_ledger()
        self._save()

    def _local_datetime(
        self,
        timestamp: datetime,
    ) -> datetime:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=datetime.now().astimezone().tzinfo
            )

        return timestamp.astimezone()

    def _load(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return self._empty_ledger()

        try:
            raw_data = json.loads(
                self.ledger_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return self._empty_ledger()

        if not isinstance(raw_data, dict):
            return self._empty_ledger()

        if raw_data.get("ledger_version") != self.LEDGER_VERSION:
            return self._empty_ledger()

        if not isinstance(raw_data.get("records"), list):
            raw_data["records"] = []

        return raw_data

    def _save(self) -> None:
        self.ledger_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self.ledger_path.with_suffix(
            self.ledger_path.suffix + ".tmp"
        )

        temporary_path.write_text(
            json.dumps(
                self._data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(self.ledger_path)

    def _empty_ledger(self) -> dict[str, Any]:
        return {
            "ledger_version": self.LEDGER_VERSION,
            "records": [],
        }