from __future__ import annotations

import re

from app.sources.source_models import (
    SourcePlatform,
    SourceProfile,
)


class SourceProfileFactory:
    """
    Creates SourceProfile objects from minimal user input.

    For the normal Reddit workflow, the user only needs to provide a
    subreddit name or subreddit URL. All internal fields are generated
    automatically.
    """

    SUBREDDIT_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?reddit\.com/r/"
        r"(?P<community>[A-Za-z0-9_]+)",
        flags=re.IGNORECASE,
    )

    VALID_COMMUNITY_PATTERN = re.compile(
        r"^[A-Za-z0-9_]+$"
    )

    def create_reddit_profile(
        self,
        subreddit: str,
        theme_hint: str = "",
    ) -> SourceProfile:
        community = self.normalize_subreddit(
            subreddit
        )

        profile_id = (
            f"reddit_{community.lower()}"
        )

        return SourceProfile(
            id=profile_id,
            name=self.humanize_community(community),
            platform=SourcePlatform.REDDIT,
            community=community,
            theme_hint=theme_hint.strip(),
        )

    def normalize_subreddit(
        self,
        subreddit: str,
    ) -> str:
        normalized_input = subreddit.strip()

        if not normalized_input:
            raise ValueError(
                "Subreddit must not be empty."
            )

        url_match = self.SUBREDDIT_URL_PATTERN.search(
            normalized_input
        )

        if url_match:
            community = url_match.group(
                "community"
            )
        else:
            community = re.sub(
                r"^/?r/",
                "",
                normalized_input,
                flags=re.IGNORECASE,
            )

            community = community.strip("/ ")

        if not community:
            raise ValueError(
                "No subreddit name could be extracted."
            )

        if not self.VALID_COMMUNITY_PATTERN.fullmatch(
            community
        ):
            raise ValueError(
                "Subreddit contains unsupported characters: "
                f"{community}"
            )

        return community

    def humanize_community(
        self,
        community: str,
    ) -> str:
        separated_camel_case = re.sub(
            r"(?<=[a-z0-9])(?=[A-Z])",
            " ",
            community,
        )

        separated_words = re.sub(
            r"[_\-]+",
            " ",
            separated_camel_case,
        )

        normalized_words = re.sub(
            r"\s+",
            " ",
            separated_words,
        ).strip()

        return normalized_words.title()