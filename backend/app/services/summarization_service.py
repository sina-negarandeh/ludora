# Known limitation, tracked in docs/roadmap.md: app/database/models.py uses
# SQLAlchemy's legacy Column(...) declarative style, not 2.0's typed
# Mapped[]/mapped_column(). Pyright can't tell an instance attribute like
# `game.rank` apart from the class-level Column descriptor, so it reports
# every read of a model attribute as Column[X] instead of X. These are
# false positives, not real bugs -- confirmed by direct behavior at
# runtime throughout this session -- and this file is unusually dense with
# them since it's mostly model-attribute plumbing. Suppressed here rather
# than project-wide so a real error of the same rule elsewhere still surfaces.
# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportReturnType=false

import hashlib
import json
import random
import time
from collections import defaultdict
from typing import Any

# Deliberately the plain SDK, not langfuse.openai (see
# assistant_service.py's import): Langfuse tracing is scoped to the AI
# Assistant only, not this offline summarization job. Importing
# langfuse.openai monkeypatches openai.resources.chat.completions.
# Completions.create/.parse at the CLASS level (confirmed directly
# against the installed SDK), not just for its own import site -- so if
# this module and assistant_service.py are EVER imported into the same
# process (they aren't today: this only runs via the standalone
# scripts/generate_summaries.py, assistant_service.py only via the live
# API), this client would silently start getting traced too.
from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ml_config import RANDOM_SEED, ABSAConfig, SummarizationConfig
from app.database.models import Game, GameAspectAggregate, GameSummary, ReviewAspect
from app.schemas.summarization import AspectMiniSummary, FinalGameSummary

# Constants
MIN_REVIEWS_FOR_ABSA = SummarizationConfig.MIN_REVIEWS_FOR_ABSA
MIN_ASPECT_MENTIONS = SummarizationConfig.MIN_ASPECT_MENTIONS
TOP_K_ASPECTS = SummarizationConfig.TOP_K_ASPECTS
MAX_REVIEWS_PER_ASPECT = SummarizationConfig.MAX_REVIEWS_PER_ASPECT

OUTCOME_LABELS = {"positive": "Positive", "negative": "Negative", "mixed_neutral": "Mixed / Neutral"}

class SummarizationService:
    def __init__(self, db: Session):
        self.db = db
        # Deliberately separate from the assistant's OPENAI_*/LLM_MODEL_NAME
        # settings — see app.core.config.Settings for why.
        self.client = OpenAI(base_url=settings.SUMMARIZATION_OPENAI_BASE_URL, api_key=settings.SUMMARIZATION_OPENAI_API_KEY)
        self.model = settings.SUMMARIZATION_MODEL_NAME
        # Seeded so the same aspect's evidence sample (and thus the same LLM
        # input) is reproducible across offline generate_summaries.py runs.
        self._rng = random.Random(RANDOM_SEED)
        # Per-call (prompt_hash, latency_seconds) log — an LLM-prompted feature's
        # "training" is really its prompt, so this is what generate_summaries.py
        # logs to MLflow instead of conventional model hyperparameters.
        self.llm_calls: list[dict] = []

    def _call_llm_json(self, system_prompt: str, user_prompt: str, schema_class) -> Any:
        schema_json = schema_class.model_json_schema()
        full_system_prompt = f"""{system_prompt}

Output ONLY valid JSON matching this schema. No markdown wrapping.
{json.dumps(schema_json, indent=2)}
"""
        prompt_hash = hashlib.sha256(full_system_prompt.encode()).hexdigest()[:12]

        # Retries, not just a single attempt: measured against this local
        # server, an identical (temperature=0) prompt occasionally comes
        # back with an empty completion (finish_reason=stop, well under
        # max_tokens) and succeeds on a byte-identical retry -- a real,
        # non-deterministic flake, not a broken prompt. One bad call
        # shouldn't abort an entire batch run.
        last_error: Exception | None = None
        for attempt in range(SummarizationConfig.MAX_LLM_RETRIES + 1):
            start = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=SummarizationConfig.TEMPERATURE,
                max_tokens=SummarizationConfig.MAX_TOKENS
            )
            latency_seconds = time.time() - start

            raw_content = response.choices[0].message.content or "{}"
            raw_content = raw_content.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            elif raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]

            try:
                result = schema_class.model_validate_json(raw_content.strip())
            except ValidationError as e:
                last_error = e
                self.llm_calls.append({
                    "schema": schema_class.__name__,
                    "prompt_hash": prompt_hash,
                    "latency_seconds": round(latency_seconds, 3),
                    "attempt": attempt + 1,
                    "failed": True,
                })
                continue

            self.llm_calls.append({
                "schema": schema_class.__name__,
                "prompt_hash": prompt_hash,
                "latency_seconds": round(latency_seconds, 3),
                "attempt": attempt + 1,
            })
            return result

        raise last_error

    def _classify_outcome(self, agg: GameAspectAggregate) -> tuple[str, float, float, float]:
        """Same Positive/Negative/Mixed-Neutral rule as the aspect cards
        (AspectService.get_game_aspects(), GameDetail.tsx) — an aspect only
        claims a confident label if that share of mentions clears
        CARD_DOMINANCE_THRESHOLD, otherwise it's genuinely split. Keeping
        this identical to the card logic means the summary paragraph can
        never contradict what the UI shows for the same aspect."""
        total = max(1, agg.total_mentions)
        pos_ratio = agg.positive_count / total
        neu_ratio = agg.neutral_count / total
        neg_ratio = agg.negative_count / total
        if pos_ratio >= ABSAConfig.CARD_DOMINANCE_THRESHOLD:
            outcome = "positive"
        elif neg_ratio >= ABSAConfig.CARD_DOMINANCE_THRESHOLD:
            outcome = "negative"
        else:
            outcome = "mixed_neutral"
        return outcome, pos_ratio, neu_ratio, neg_ratio

    def _sample_reviews(self, game_id: int, aspect: str) -> list[ReviewAspect]:
        # Same confidence bar as aggregation (ABSAConfig.WINNER_PROB_THRESHOLD)
        # and the same three sentiments as the card system -- evidence fed to
        # the LLM must be exactly what's being counted, not a superset that
        # includes low-confidence or (pre-redesign) never-filtered rows.
        reviews = self.db.query(ReviewAspect).filter(
            ReviewAspect.game_id == game_id,
            ReviewAspect.aspect == aspect,
            ReviewAspect.sentiment.in_(("positive", "negative", "neutral")),
            ReviewAspect.confidence >= ABSAConfig.WINNER_PROB_THRESHOLD,
            ReviewAspect.evidence.isnot(None)
        ).all()

        if len(reviews) <= MAX_REVIEWS_PER_ASPECT:
            return reviews
            
        # Proportionate sampling
        sentiment_groups = defaultdict(list)
        for r in reviews:
            sentiment_groups[r.sentiment].append(r)
            
        sampled = []
        for _sentiment, group_reviews in sentiment_groups.items():
            proportion = len(group_reviews) / len(reviews)
            sample_size = max(1, int(MAX_REVIEWS_PER_ASPECT * proportion))
            # Shuffle safely for sampling (seeded — see __init__)
            self._rng.shuffle(group_reviews)
            sampled.extend(group_reviews[:sample_size])
            
        # Ensure we don't exceed MAX exactly due to rounding
        return sampled[:MAX_REVIEWS_PER_ASPECT]

    def _summarize_aspect(self, aspect: str, reviews: list[ReviewAspect], outcome: str, pos_ratio: float, neu_ratio: float, neg_ratio: float) -> AspectMiniSummary:
        positive = sum(1 for r in reviews if r.sentiment == 'positive')
        negative = sum(1 for r in reviews if r.sentiment == 'negative')
        neutral = sum(1 for r in reviews if r.sentiment == 'neutral')

        system_prompt = """/no_think
You are an expert sentiment analyst summarizing product reviews.
Write a 1-sentence mini-summary of what customers say about the given aspect based on the provided evidence.
The "Overall verdict" below is computed from the full review set (not just the evidence shown) and is
ground truth -- your summary must be consistent with it, not contradict it based on the sampled evidence alone.
Note any prominent caveats."""

        evidence_text = "\n".join([f"- [{r.sentiment}] {r.evidence}" for r in reviews])

        user_prompt = f"""Aspect: {aspect}
Overall verdict: {OUTCOME_LABELS[outcome]} ({pos_ratio:.0%} positive / {neu_ratio:.0%} neutral / {neg_ratio:.0%} negative across all qualifying mentions)
Evidence sample ({len(reviews)} of the mentions above; Positive: {positive}, Negative: {negative}, Neutral: {neutral}):
{evidence_text}"""

        mini_summary = self._call_llm_json(system_prompt, user_prompt, AspectMiniSummary)
        # Override the LLM's own sentiment guess with the computed ground
        # truth -- it should never be able to drift from what the aspect
        # card shows for the same aspect.
        mini_summary.sentiment = OUTCOME_LABELS[outcome]
        return mini_summary

    def generate_game_summary(self, game_id: int) -> GameSummary | None:
        # 1. Verify >= MIN_REVIEWS_FOR_ABSA
        # Distinct reviews, not raw review_aspects rows -- one review can
        # produce several aspect rows, so counting rows overstated how many
        # actual reviews were behind the number (e.g. Brass: Birmingham had
        # 175 rows from only 112 distinct reviews). Also applies the same
        # confidence bar as everything else in this pipeline, so this gate
        # measures "reviews with usable signal," not "reviews attempted."
        total_reviews = self.db.query(func.count(func.distinct(ReviewAspect.review_id))).filter(
            ReviewAspect.game_id == game_id,
            ReviewAspect.sentiment.in_(("positive", "negative", "neutral")),
            ReviewAspect.confidence >= ABSAConfig.WINNER_PROB_THRESHOLD,
        ).scalar()
        if total_reviews < MIN_REVIEWS_FOR_ABSA:
            print(f"Skipping game {game_id}: Not enough qualifying reviews ({total_reviews} < {MIN_REVIEWS_FOR_ABSA})")
            return None

        game = self.db.query(Game).filter(Game.bgg_id == game_id).first()
        if not game:
            return None

        # 2. Get top K aspects
        aggregates = self.db.query(GameAspectAggregate).filter(
            GameAspectAggregate.game_id == game_id,
            GameAspectAggregate.total_mentions >= MIN_ASPECT_MENTIONS
        ).order_by(GameAspectAggregate.total_mentions.desc()).limit(TOP_K_ASPECTS).all()

        if not aggregates:
            print(f"Skipping game {game_id}: No aspects with >={MIN_ASPECT_MENTIONS} mentions.")
            return None

        # 3. Process each aspect
        mini_summaries = []
        for agg in aggregates:
            sampled_reviews = self._sample_reviews(game_id, agg.aspect)
            if not sampled_reviews:
                continue

            outcome, pos_ratio, neu_ratio, neg_ratio = self._classify_outcome(agg)
            print(f"Summarizing aspect: {agg.aspect} ({len(sampled_reviews)} samples, verdict={OUTCOME_LABELS[outcome]})")
            try:
                mini_summary = self._summarize_aspect(agg.aspect, sampled_reviews, outcome, pos_ratio, neu_ratio, neg_ratio)
            except ValidationError:
                # Retries in _call_llm_json already absorb the common
                # transient case (empty completion); if it's still failing
                # after those, skip this one aspect rather than losing the
                # whole game's summary over it -- especially important once
                # this runs across many games unattended.
                print(f"  Skipping aspect {agg.aspect}: LLM response invalid after {SummarizationConfig.MAX_LLM_RETRIES + 1} attempts.")
                continue
            mini_summaries.append(mini_summary)

        if not mini_summaries:
            return None

        # 4. Final Summarization Stage
        system_prompt = """/no_think
Write a "Customers say" summary for this product.
Use the structured themes below.

Requirements:
- 2-3 sentences.
- Start with the strongest overall positive themes.
- Mention important negative/mixed feedback when present.
- Do not mention every aspect.
- Do not invent information.
- Do not make absolute claims.
- Do not mention review counts.
- Preserve uncertainty when the evidence is mixed.
- Use natural customer-facing language.
- Every factual claim must be supported by one or more supplied themes."""

        themes_text = ""
        for m in mini_summaries:
            themes_text += f"\nAspect: {m.aspect}\nSentiment: {m.sentiment}\nSummary: {m.summary}\nConfidence: {m.confidence}\n"

        user_prompt = f"Product: {game.name}\n\nTHEMES:\n{themes_text}"
        
        print(f"Generating final summary for {game.name}...")
        try:
            final_summary_data = self._call_llm_json(system_prompt, user_prompt, FinalGameSummary)
        except ValidationError:
            print(f"Skipping game {game_id}: final synthesis LLM response invalid after {SummarizationConfig.MAX_LLM_RETRIES + 1} attempts.")
            return None

        # 5. Save to DB
        existing_summary = self.db.query(GameSummary).filter(GameSummary.game_id == game_id).first()
        if existing_summary:
            existing_summary.summary = final_summary_data.summary
            existing_summary.model_used = self.model
            existing_summary.created_at = func.now()
            db_obj = existing_summary
        else:
            db_obj = GameSummary(
                game_id=game_id,
                summary=final_summary_data.summary,
                model_used=self.model
            )
            self.db.add(db_obj)
            
        self.db.commit()
        self.db.refresh(db_obj)
        
        return db_obj
