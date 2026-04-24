from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings


@dataclass(frozen=True)
class LocalIntentEntry:
    question: str
    normalized_question: str
    tokens: set[str]
    stems: set[str]
    trigrams: set[str]
    payload: dict[str, Any]


class LocalIntentModel:
    def __init__(self) -> None:
        self._entries: list[LocalIntentEntry] = []
        self._loaded = False

    def extract_json_with_trace(self, user_prompt: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        self._ensure_loaded()
        if not self._entries:
            return None, {"status": "model_missing", "entries": 0}

        normalized_question = self._normalize(user_prompt)
        question_tokens = self._tokens(normalized_question)
        if not question_tokens:
            return None, {"status": "empty_question", "entries": len(self._entries)}

        best_score = 0.0
        second_score = 0.0
        best_entry: LocalIntentEntry | None = None
        normalized_stems = self._stems(question_tokens)
        normalized_trigrams = self._trigrams(normalized_question)
        for item in self._entries:
            score = self._score(question_tokens, normalized_stems, normalized_trigrams, item)
            if score > best_score:
                second_score = best_score
                best_score = score
                best_entry = item
            elif score > second_score:
                second_score = score

        margin = best_score - second_score
        if not best_entry or best_score < settings.local_intent_min_similarity:
            return None, {
                "status": "no_match",
                "best_score": round(best_score, 4),
                "second_score": round(second_score, 4),
                "margin": round(margin, 4),
                "threshold": settings.local_intent_min_similarity,
                "min_margin": settings.local_intent_min_margin,
                "entries": len(self._entries),
            }

        # Near-duplicate paraphrases can produce equal scores; keep strict margin only for weak matches.
        if margin < settings.local_intent_min_margin and best_score < 0.30:
            return None, {
                "status": "no_match",
                "best_score": round(best_score, 4),
                "second_score": round(second_score, 4),
                "margin": round(margin, 4),
                "threshold": settings.local_intent_min_similarity,
                "min_margin": settings.local_intent_min_margin,
                "entries": len(self._entries),
            }

        payload = dict(best_entry.payload)
        payload["question"] = user_prompt
        payload["confidence"] = round(max(payload.get("confidence", 0.6), min(0.98, best_score + 0.2)), 2)
        return payload, {
            "status": "ok",
            "matched_question": best_entry.question,
            "similarity": round(best_score, 4),
            "second_score": round(second_score, 4),
            "margin": round(margin, 4),
            "entries": len(self._entries),
        }

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        model_path = Path(settings.local_intent_model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[2] / model_path
        if not model_path.exists():
            self._entries = []
            return
        try:
            raw = json.loads(model_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._entries = []
            return

        entries = raw.get("entries", []) if isinstance(raw, dict) else []
        parsed: list[LocalIntentEntry] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            question = item.get("question")
            payload = item.get("payload")
            if not isinstance(question, str) or not isinstance(payload, dict):
                continue
            normalized = self._normalize(question)
            tokens = self._tokens(normalized)
            parsed.append(
                LocalIntentEntry(
                    question=question,
                    normalized_question=normalized,
                    tokens=tokens,
                    stems=self._stems(tokens),
                    trigrams=self._trigrams(normalized),
                    payload=payload,
                )
            )
        self._entries = parsed

    def _normalize(self, value: str) -> str:
        cleaned = value.lower().replace("ё", "е")
        cleaned = re.sub(r"[,;:!?()\[\]{}\"'`]+", " ", cleaned)
        cleaned = re.sub(
            r"\b(пожалуйста|плиз|будь добр|будь добра|будьте добры|подскажи|можешь|хочу понять|нужно понять|скажи)\b",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _tokens(self, value: str) -> set[str]:
        stop_words = {"и", "в", "на", "по", "за", "с", "к", "до", "от", "о", "а", "или", "ли", "же", "бы", "мне", "у", "нас"}
        return {token for token in value.split(" ") if token and len(token) > 1 and token not in stop_words}

    def _stems(self, tokens: set[str]) -> set[str]:
        suffixes = (
            "иями",
            "ями",
            "ами",
            "ого",
            "ему",
            "ому",
            "ыми",
            "ими",
            "иях",
            "ах",
            "ях",
            "ов",
            "ев",
            "ия",
            "ий",
            "ой",
            "ая",
            "ое",
            "ые",
            "ые",
            "ых",
            "ую",
            "ть",
            "ти",
            "ся",
            "сь",
            "а",
            "я",
            "ы",
            "и",
            "е",
            "о",
            "у",
        )
        stems: set[str] = set()
        for token in tokens:
            stem = token
            for suffix in suffixes:
                if len(stem) > 4 and stem.endswith(suffix):
                    stem = stem[: -len(suffix)]
                    break
            stems.add(stem)
        return stems

    def _trigrams(self, value: str) -> set[str]:
        compact = value.replace(" ", "_")
        if len(compact) < 3:
            return {compact} if compact else set()
        return {compact[index : index + 3] for index in range(len(compact) - 2)}

    def _similarity(self, source: set[str], target: set[str]) -> float:
        if not source or not target:
            return 0.0
        overlap = source.intersection(target)
        union = source.union(target)
        return len(overlap) / len(union)

    def _score(
        self,
        source_tokens: set[str],
        source_stems: set[str],
        source_trigrams: set[str],
        entry: LocalIntentEntry,
    ) -> float:
        token_score = self._similarity(source_tokens, entry.tokens)
        stem_score = self._similarity(source_stems, entry.stems)
        trigram_score = self._similarity(source_trigrams, entry.trigrams)
        coverage = (len(source_stems.intersection(entry.stems)) / max(1, len(source_stems))) if source_stems else 0.0
        return round(token_score * 0.45 + stem_score * 0.25 + trigram_score * 0.2 + coverage * 0.1, 6)


local_intent_model = LocalIntentModel()
