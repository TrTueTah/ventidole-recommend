"""
Cold-Start Recommendation Strategy

Handles recommendations for new users who have minimal or no interaction history.
Uses a deterministic ranking approach based on:
- Community match (primary signal from followed communities)
- Content similarity (tags and community metadata)
- Recency (time-decay to keep feed fresh)
- Community popularity (engagement within followed communities)
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple, Any, Optional
import numpy as np
from dataclasses import dataclass
from enum import Enum

from config import (
    COLD_START_INTERACTION_THRESHOLD,
    COLD_START_RECENCY_WINDOW_DAYS,
    COLD_START_WEIGHT_COMMUNITY,
    COLD_START_WEIGHT_CONTENT,
    COLD_START_WEIGHT_RECENCY,
    COLD_START_WEIGHT_POPULARITY
)
from data.load_data import load_user_followed_communities

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserState(Enum):
    """User state for recommendation strategy selection"""
    COLD_START = "cold_start"
    NORMAL = "normal"


@dataclass
class PostCandidate:
    """Post candidate with computed scores for cold-start ranking"""
    post_id: str
    community_id: str
    tags: List[str]
    created_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    metadata: Dict[str, Any]

    # Computed scores
    community_score: float = 0.0
    content_score: float = 0.0
    recency_score: float = 0.0
    popularity_score: float = 0.0
    final_score: float = 0.0


class ColdStartStrategy:
    """
    Cold-start recommendation strategy for new users.

    Uses a deterministic scoring approach:
    final_score = w1 * community_match + w2 * content_similarity + w3 * recency + w4 * popularity

    This is NOT a model - it's a rule-based ranking layer.
    """

    def __init__(
        self,
        interaction_threshold: int = None,
        recency_window_days: int = None,
        weight_community: float = None,
        weight_content: float = None,
        weight_recency: float = None,
        weight_popularity: float = None
    ):
        """
        Initialize cold-start strategy with configurable parameters.

        Args:
            interaction_threshold: Number of interactions to consider user as "normal"
            recency_window_days: Time window for recency decay calculation
            weight_community: Weight for community match score (0-1)
            weight_content: Weight for content similarity score (0-1)
            weight_recency: Weight for recency score (0-1)
            weight_popularity: Weight for popularity score (0-1)
        """
        self.interaction_threshold = interaction_threshold or COLD_START_INTERACTION_THRESHOLD
        self.recency_window_days = recency_window_days or COLD_START_RECENCY_WINDOW_DAYS
        self.weight_community = weight_community or COLD_START_WEIGHT_COMMUNITY
        self.weight_content = weight_content or COLD_START_WEIGHT_CONTENT
        self.weight_recency = weight_recency or COLD_START_WEIGHT_RECENCY
        self.weight_popularity = weight_popularity or COLD_START_WEIGHT_POPULARITY

        # Data caches (populated by model manager)
        self.user_interaction_counts: Dict[str, int] = {}
        self.user_followed_communities: Dict[str, Set[str]] = {}
        self.community_dominant_tags: Dict[str, Dict[str, int]] = {}
        self.posts_data: Dict[str, Dict[str, Any]] = {}
        self.community_max_engagement: Dict[str, float] = {}

        logger.info(
            f"ColdStartStrategy initialized: threshold={self.interaction_threshold}, "
            f"weights=[community={self.weight_community}, content={self.weight_content}, "
            f"recency={self.weight_recency}, popularity={self.weight_popularity}]"
        )

    def detect_user_state(self, user_id: str) -> UserState:
        """
        Detect if user is in cold-start or normal state.

        Args:
            user_id: User ID to check

        Returns:
            UserState.COLD_START if interactions < threshold, else UserState.NORMAL
        """
        interaction_count = self.user_interaction_counts.get(user_id, 0)

        if interaction_count < self.interaction_threshold:
            logger.debug(f"User {user_id} is COLD_START (interactions={interaction_count})")
            return UserState.COLD_START
        else:
            logger.debug(f"User {user_id} is NORMAL (interactions={interaction_count})")
            return UserState.NORMAL

    def get_user_interaction_count(self, user_id: str) -> int:
        """Get the number of interactions for a user."""
        return self.user_interaction_counts.get(user_id, 0)

    def get_user_followed_communities(self, user_id: str) -> Set[str]:
        """
        Get the set of community IDs that a user follows.
        Falls back to database for new users not in cache.
        """
        # Check cache first
        if user_id in self.user_followed_communities:
            return self.user_followed_communities[user_id]

        # Fall back to database for new users
        try:
            communities = load_user_followed_communities(user_id)
            if communities:
                community_set = set(communities)
                # Cache for future requests
                self.user_followed_communities[user_id] = community_set
                logger.info(f"Loaded {len(community_set)} followed communities for new user {user_id}")
                return community_set
        except Exception as e:
            logger.error(f"Error loading followed communities for user {user_id}: {e}")

        return set()

    def compute_community_score(self, post_community_id: str, followed_communities: Set[str]) -> float:
        """
        Compute community match score.

        Binary score: 1.0 if post is from a followed community, 0.0 otherwise.
        Future enhancement: could add weak community matching (similar communities).

        Args:
            post_community_id: Community ID of the post
            followed_communities: Set of community IDs the user follows

        Returns:
            1.0 if match, 0.0 otherwise
        """
        return 1.0 if post_community_id in followed_communities else 0.0

    def compute_content_score(
        self,
        post_tags: List[str],
        post_community_id: str,
        followed_communities: Set[str]
    ) -> float:
        """
        Compute content similarity score.

        Uses tag overlap between post tags and dominant tags of followed communities.

        Args:
            post_tags: Tags associated with the post
            post_community_id: Community ID of the post
            followed_communities: Set of community IDs the user follows

        Returns:
            Content similarity score (0.0 to 1.0)
        """
        if not post_tags or not followed_communities:
            return 0.0

        # Build user's tag profile from followed communities
        user_tags: Dict[str, int] = {}
        for comm_id in followed_communities:
            comm_tags = self.community_dominant_tags.get(comm_id, {})
            for tag, count in comm_tags.items():
                user_tags[tag] = user_tags.get(tag, 0) + count

        if not user_tags:
            return 0.0

        # Calculate tag overlap
        post_tag_set = set(post_tags)
        user_tag_set = set(user_tags.keys())
        overlap = post_tag_set.intersection(user_tag_set)

        if not overlap:
            return 0.0

        # Weighted Jaccard-like similarity
        # Weight overlapping tags by their frequency in user's communities
        overlap_weight = sum(user_tags.get(tag, 0) for tag in overlap)
        total_weight = sum(user_tags.values())

        return overlap_weight / total_weight if total_weight > 0 else 0.0

    def compute_recency_score(self, created_at: datetime, reference_time: datetime = None) -> float:
        """
        Compute recency score with time decay.

        Uses linear decay within the configured window:
        - Posts within window get score from 1.0 (newest) to 0.0 (oldest in window)
        - Posts older than window get 0.0

        Args:
            created_at: When the post was created
            reference_time: Reference time for calculation (defaults to now)

        Returns:
            Recency score (0.0 to 1.0)
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        # Handle naive datetime
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        age_seconds = (reference_time - created_at).total_seconds()
        age_days = age_seconds / (24 * 3600)

        if age_days < 0:
            return 1.0  # Future posts get max score
        if age_days > self.recency_window_days:
            return 0.0  # Old posts get zero

        # Linear decay within window
        return max(0.0, 1.0 - (age_days / self.recency_window_days))

    def compute_popularity_score(
        self,
        post_id: str,
        community_id: str,
        view_count: int,
        like_count: int,
        comment_count: int
    ) -> float:
        """
        Compute popularity score within the post's community.

        Uses engagement metrics normalized by max engagement in the community.

        Args:
            post_id: Post ID
            community_id: Community ID
            view_count: Number of views
            like_count: Number of likes
            comment_count: Number of comments

        Returns:
            Popularity score (0.0 to 1.0)
        """
        # Compute engagement score (weighted sum of metrics)
        engagement = view_count + (like_count * 3) + (comment_count * 5)

        # Normalize by community's max engagement
        max_engagement = self.community_max_engagement.get(community_id, 1.0)
        if max_engagement <= 0:
            max_engagement = 1.0

        return min(1.0, engagement / max_engagement)

    def compute_final_score(self, candidate: PostCandidate) -> float:
        """
        Compute final score for a post candidate.

        final_score = w1 * community + w2 * content + w3 * recency + w4 * popularity

        Args:
            candidate: PostCandidate with individual scores computed

        Returns:
            Final weighted score
        """
        return (
            self.weight_community * candidate.community_score +
            self.weight_content * candidate.content_score +
            self.weight_recency * candidate.recency_score +
            self.weight_popularity * candidate.popularity_score
        )

    def get_cold_start_recommendations(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Tuple[str, float, Dict[str, Any]]], int]:
        """
        Generate recommendations for a cold-start user.

        Strategy:
        1. Filter posts to only those from followed communities
        2. Score each post using the cold-start formula
        3. Sort by score and apply pagination

        Args:
            user_id: User ID to generate recommendations for
            limit: Number of recommendations to return
            offset: Pagination offset

        Returns:
            Tuple of (list of (post_id, score, metadata), total_count)
        """
        followed_communities = self.get_user_followed_communities(user_id)
        logger.info(f"Generating cold-start recommendations for user {user_id} "
                    f"(follows {len(followed_communities)} communities)")

        if not followed_communities:
            logger.warning(f"User {user_id} follows no communities, returning empty recommendations")
            return [], 0

        reference_time = datetime.now(timezone.utc)
        candidates: List[PostCandidate] = []

        # Build candidates from posts in followed communities
        for post_id, post_data in self.posts_data.items():
            community_id = post_data.get('communityId')

            # CRITICAL: Only include posts from followed communities
            if community_id not in followed_communities:
                continue

            # Extract post data
            metadata = post_data.get('metadata', {})
            tags = metadata.get('tags', []) if isinstance(metadata, dict) else []
            created_at = post_data.get('createdAt')
            if created_at is None:
                created_at = datetime.now(timezone.utc)

            candidate = PostCandidate(
                post_id=post_id,
                community_id=community_id,
                tags=tags,
                created_at=created_at,
                view_count=post_data.get('view_count', 0),
                like_count=post_data.get('like_count', 0),
                comment_count=post_data.get('comment_count', 0),
                metadata={'metadata': metadata, 'communityId': community_id}
            )

            # Compute individual scores
            candidate.community_score = self.compute_community_score(
                community_id, followed_communities
            )
            candidate.content_score = self.compute_content_score(
                tags, community_id, followed_communities
            )
            candidate.recency_score = self.compute_recency_score(
                created_at, reference_time
            )
            candidate.popularity_score = self.compute_popularity_score(
                post_id, community_id,
                candidate.view_count,
                candidate.like_count,
                candidate.comment_count
            )

            # Compute final score
            candidate.final_score = self.compute_final_score(candidate)
            candidates.append(candidate)

        # Sort by final score (descending)
        candidates.sort(key=lambda x: x.final_score, reverse=True)
        total_count = len(candidates)

        # Apply pagination
        paginated = candidates[offset:offset + limit]

        # Convert to output format
        results = [
            (c.post_id, c.final_score, c.metadata)
            for c in paginated
        ]

        logger.info(f"Generated {len(results)} cold-start recommendations "
                    f"(total candidates: {total_count})")

        return results, total_count

    def load_data(
        self,
        user_interaction_counts: Dict[str, int],
        user_followed_communities: Dict[str, Set[str]],
        community_dominant_tags: Dict[str, Dict[str, int]],
        posts_data: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Load data caches required for cold-start recommendations.

        This should be called by ModelManager after loading data from database.

        Args:
            user_interaction_counts: Dict of user_id -> interaction_count
            user_followed_communities: Dict of user_id -> set of community_ids
            community_dominant_tags: Dict of community_id -> {tag: count}
            posts_data: Dict of post_id -> {metadata, communityId, createdAt, counts}
        """
        self.user_interaction_counts = user_interaction_counts
        self.user_followed_communities = user_followed_communities
        self.community_dominant_tags = community_dominant_tags
        self.posts_data = posts_data

        # Compute max engagement per community
        self._compute_community_max_engagement()

        logger.info(
            f"ColdStartStrategy data loaded: "
            f"{len(user_interaction_counts)} users with interactions, "
            f"{len(user_followed_communities)} users with followed communities, "
            f"{len(community_dominant_tags)} communities with tags, "
            f"{len(posts_data)} posts"
        )

    def _compute_community_max_engagement(self) -> None:
        """Compute maximum engagement score per community for normalization."""
        community_engagements: Dict[str, List[float]] = {}

        for post_data in self.posts_data.values():
            community_id = post_data.get('communityId')
            if not community_id:
                continue

            engagement = (
                post_data.get('view_count', 0) +
                post_data.get('like_count', 0) * 3 +
                post_data.get('comment_count', 0) * 5
            )

            if community_id not in community_engagements:
                community_engagements[community_id] = []
            community_engagements[community_id].append(engagement)

        # Store max for each community
        for comm_id, engagements in community_engagements.items():
            self.community_max_engagement[comm_id] = max(engagements) if engagements else 1.0

        logger.debug(f"Computed max engagement for {len(self.community_max_engagement)} communities")
