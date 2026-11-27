"""
Live question de-semanticization (skeleton masking) for unseen user queries.

Exact same masking rules as `src/skeleton/masking.py` (Guo et al., 2023 simplified):
  1. numbers (POS NUM or digits),
  2. values inside spaCy entities with NOUN/PROPN, or NORP (nationalities),
  3. content words whose lemma appears in the target DB's table/column names,
  4. quoted strings ('Fail', "Homeland Security").
INTENT_WORDS are protected from rules 1-3 so SQL aggregation/ordering intent stays intact.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MASK = "[MASK]"
CONTENT_POS = {"NOUN", "PROPN", "ADJ", "VERB", "NUM"}
ENTITY_POS = {"NOUN", "PROPN"}
INTENT_WORDS = frozenset(
    """
    number total count average avg sum maximum max minimum min
    most least highest lowest largest smallest order distinct different have be
    """.split()
)
_QUOTED = re.compile(r"\"[^\"]+\"|(?<!\w)'[^']+'(?!\w)")


class LiveSkeletonMasker:
    """Loads spaCy once at startup and masks incoming questions on the fly."""

    def __init__(self, spacy_model: str = "en_core_web_sm") -> None:
        import spacy

        self.nlp = spacy.load(spacy_model)
        # Keep "id" as one token instead of splitting like "I'd" (-> "i", "d")
        self.nlp.tokenizer.rules = {
            k: v for k, v in self.nlp.tokenizer.rules.items() if k.lower() != "id"
        }
        self._schema_words_cache: dict[str, set[str]] = {}
        logger.info("Loaded spaCy model %s for live skeleton masking", spacy_model)

    def register_db(self, db_id: str, raw_db_entry: dict[str, Any]) -> set[str]:
        """Precompute lemmatized schema vocabulary for a Spider tables.json DB entry."""
        names = list(raw_db_entry.get("table_names", raw_db_entry.get("table_names_original", [])))
        col_names = raw_db_entry.get("column_names", raw_db_entry.get("column_names_original", []))
        names.extend(name for _, name in col_names[1:])  # index 0 is "*"
        words = {t.lemma_.lower() for doc in self.nlp.pipe(names) for t in doc}
        self._schema_words_cache[db_id] = words
        return words

    def mask(self, question: str, db_id: str) -> str:
        """Mask an unseen natural-language question using the target DB's schema words."""
        words = self._schema_words_cache.get(db_id, set())
        doc = self.nlp(question)
        quoted = [(m.start() + 1, m.end() - 1) for m in _QUOTED.finditer(doc.text)]
        out: list[str] = []
        for t in doc:
            lemma = t.lemma_.lower()
            masked = any(a <= t.idx < b for a, b in quoted) or (
                t.lower_ not in INTENT_WORDS
                and lemma not in INTENT_WORDS
                and (
                    t.pos_ == "NUM"
                    or t.is_digit
                    or (bool(t.ent_type_) and t.pos_ in ENTITY_POS)
                    or t.ent_type_ == "NORP"
                    or (t.pos_ in CONTENT_POS and lemma in words)
                )
            )
            out.append((MASK if masked else t.text) + t.whitespace_)
        return "".join(out)
