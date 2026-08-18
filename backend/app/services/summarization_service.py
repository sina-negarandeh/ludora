import hashlib
import json
import random
import time
from typing import List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from openai import OpenAI
from collections import defaultdict

from app.core.config import settings
from app.core.ml_config import RANDOM_SEED, SummarizationConfig
from app.database.models import Game, ReviewAspect, GameAspectAggregate, GameSummary
from app.schemas.summarization import AspectMiniSummary, FinalGameSummary

# Constants
MIN_REVIEWS_FOR_ABSA = SummarizationConfig.MIN_REVIEWS_FOR_ABSA
MIN_ASPECT_MENTIONS = SummarizationConfig.MIN_ASPECT_MENTIONS
TOP_K_ASPECTS = SummarizationConfig.TOP_K_ASPECTS
MAX_REVIEWS_PER_ASPECT = SummarizationConfig.MAX_REVIEWS_PER_ASPECT

class SummarizationService:
    def __init__(self, db: Session):
        self.db = db
        self.client = OpenAI(base_url=settings.OPENAI_BASE_URL, api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL_NAME
        # Seeded so the same aspect's evidence sample (and thus the same LLM
        # input) is reproducible across offline generate_summaries.py runs.
        self._rng = random.Random(RANDOM_SEED)
        # Per-call (prompt_hash, latency_seconds) log — an LLM-prompted feature's
        # "training" is really its prompt, so this is what generate_summaries.py
        # logs to MLflow instead of conventional model hyperparameters.
        self.llm_calls: List[dict] = []

    def _call_llm_json(self, system_prompt: str, user_prompt: str, schema_class) -> Any:
        schema_json = schema_class.model_json_schema()
        full_system_prompt = f"""{system_prompt}

Output ONLY valid JSON matching this schema. No markdown wrapping.
{json.dumps(schema_json, indent=2)}
"""
        prompt_hash = hashlib.sha256(full_system_prompt.encode()).hexdigest()[:12]
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
        self.llm_calls.append({
            "schema": schema_class.__name__,
            "prompt_hash": prompt_hash,
            "latency_seconds": round(latency_seconds, 3),
        })

        raw_content = response.choices[0].message.content or "{}"
        raw_content = raw_content.strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        elif raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
            
        return schema_class.model_validate_json(raw_content.strip())

    def _sample_reviews(self, game_id: int, aspect: str) -> List[ReviewAspect]:
        reviews = self.db.query(ReviewAspect).filter(
            ReviewAspect.game_id == game_id,
            ReviewAspect.aspect == aspect,
            ReviewAspect.evidence.isnot(None)
        ).all()
        
        if len(reviews) <= MAX_REVIEWS_PER_ASPECT:
            return reviews
            
        # Proportionate sampling
        sentiment_groups = defaultdict(list)
        for r in reviews:
            sentiment_groups[r.sentiment].append(r)
            
        sampled = []
        for sentiment, group_reviews in sentiment_groups.items():
            proportion = len(group_reviews) / len(reviews)
            sample_size = max(1, int(MAX_REVIEWS_PER_ASPECT * proportion))
            # Shuffle safely for sampling (seeded — see __init__)
            self._rng.shuffle(group_reviews)
            sampled.extend(group_reviews[:sample_size])
            
        # Ensure we don't exceed MAX exactly due to rounding
        return sampled[:MAX_REVIEWS_PER_ASPECT]

    def _summarize_aspect(self, aspect: str, reviews: List[ReviewAspect]) -> AspectMiniSummary:
        positive = sum(1 for r in reviews if r.sentiment == 'positive')
        negative = sum(1 for r in reviews if r.sentiment == 'negative')
        mixed = sum(1 for r in reviews if r.sentiment == 'mixed')
        
        system_prompt = """You are an expert sentiment analyst summarizing product reviews.
Write a 1-sentence mini-summary of what customers say about the given aspect based on the provided evidence.
Your summary should accurately reflect the consensus and note any prominent caveats."""

        evidence_text = "\n".join([f"- [{r.sentiment}] {r.evidence}" for r in reviews])
        
        user_prompt = f"""Aspect: {aspect}
Mention Count: {len(reviews)} (Positive: {positive}, Negative: {negative}, Mixed: {mixed})

Evidence:
{evidence_text}"""

        return self._call_llm_json(system_prompt, user_prompt, AspectMiniSummary)

    def generate_game_summary(self, game_id: int) -> Optional[GameSummary]:
        # 1. Verify >= MIN_REVIEWS_FOR_ABSA
        total_reviews = self.db.query(ReviewAspect).filter(ReviewAspect.game_id == game_id).count()
        if total_reviews < MIN_REVIEWS_FOR_ABSA:
            print(f"Skipping game {game_id}: Not enough review aspects ({total_reviews} < {MIN_REVIEWS_FOR_ABSA})")
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
            
            print(f"Summarizing aspect: {agg.aspect} ({len(sampled_reviews)} samples)")
            mini_summary = self._summarize_aspect(agg.aspect, sampled_reviews)
            mini_summaries.append(mini_summary)

        if not mini_summaries:
            return None

        # 4. Final Summarization Stage
        system_prompt = """Write a "Customers say" summary for this product.
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
        final_summary_data = self._call_llm_json(system_prompt, user_prompt, FinalGameSummary)
        
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
