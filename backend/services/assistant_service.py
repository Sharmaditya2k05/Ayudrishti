"""Retrieval-augmented yoga assistant.

Grounded in two sources: the ten-asana library already in this codebase
(descriptions, benefits, cues, contraindications) and a small curated
knowledge base in ``data/knowledge/`` (philosophy, pranayama, meditation,
safety, getting started). Retrieval is TF-IDF + cosine similarity over that
handful of documents -- the right-sized tool for a few dozen documents. A
vector database would be solving a scaling problem this corpus does not
have. Generation is a single Groq chat completion given only the retrieved
context, so every answer can be traced back to what informed it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

import httpx
from sklearn.feature_extraction import text as sk_text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..core.config import settings
from .engines import get_registry

logger = logging.getLogger(__name__)

# Standard English stop words. An earlier version also dropped "yoga", "pose"
# and "asana" as too-common-to-discriminate -- but that broke short, on-topic
# questions like "what is yoga", which then had *no* searchable terms left.
# TF-IDF's own IDF weighting already down-ranks ubiquitous words.
_STOP_SET = set(sk_text.ENGLISH_STOP_WORDS)
_TOKEN_RE = re.compile(r"[a-z]+")

# Suffixes stripped longest-first, so "-ization"/"-ation" win over "-s". The
# ordering matters: "meditation" -> (-ation) "medit" and "meditate" -> (-ate)
# "medit" must converge, so "-ation" is tried before "-ate".
_SUFFIXES = (
    "izations", "ization", "izing", "ations", "ation", "ates", "ate",
    "ings", "ing", "ness", "ments", "ment", "ions", "ion", "ies", "ied",
    "ers", "er", "est", "ed", "es", "s",
)


def _stem(token: str) -> str:
    """A deliberately light stemmer -- enough to unify the word-form pairs
    that matter here ("breathe"/"breathing"/"breath", "meditate"/"meditation",
    "pose"/"poses") without pulling in a heavyweight NLP dependency."""
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    if len(token) > 3 and token.endswith("e"):
        token = token[:-1]
    return token


def _analyzer(doc: str) -> List[str]:
    """Tokenize, drop stop words, stem, and add adjacent bigrams. Stop-word
    removal happens on the raw word (before stemming) so the standard English
    list still matches."""
    tokens = [
        _stem(t)
        for t in _TOKEN_RE.findall(doc.lower())
        if len(t) > 1 and t not in _STOP_SET
    ]
    grams = list(tokens)
    grams.extend(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))
    return grams


class AssistantUnavailable(Exception):
    """Raised when GROQ_API_KEY is not configured."""


@dataclass
class KnowledgeChunk:
    id: str
    title: str
    kind: str  # "asana" | "article"
    text: str


def _asana_chunks() -> List[KnowledgeChunk]:
    chunks: List[KnowledgeChunk] = []
    for config in get_registry().all():
        parts = [
            f"{config.english_name} ({config.name}) -- {config.difficulty} difficulty.",
            config.description,
        ]
        if config.benefits:
            parts.append("Benefits: " + "; ".join(config.benefits) + ".")
        if config.cues:
            parts.append("How to do it: " + " ".join(config.cues))
        if config.contraindications:
            parts.append(
                "Avoid or take care if: " + "; ".join(config.contraindications) + "."
            )
        chunks.append(
            KnowledgeChunk(
                id=f"asana:{config.id}",
                title=config.english_name,
                kind="asana",
                text=" ".join(parts),
            )
        )
    return chunks


def _article_chunks() -> List[KnowledgeChunk]:
    chunks: List[KnowledgeChunk] = []
    directory = Path(settings.knowledge_dir)
    if not directory.exists():
        return chunks
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip() if text else path.stem
        chunks.append(
            KnowledgeChunk(id=f"article:{path.stem}", title=title, kind="article", text=text)
        )
    return chunks


@lru_cache
def _knowledge_base() -> List[KnowledgeChunk]:
    return _asana_chunks() + _article_chunks()


@lru_cache
def _vectorizer_and_matrix():
    kb = _knowledge_base()
    vectorizer = TfidfVectorizer(
        # Custom analyzer handles stop words, light stemming and bigrams (see
        # _analyzer). Stemming lets "how to breathe" find the "breath control"
        # article and "how to meditate" find "meditation".
        analyzer=_analyzer,
        # Dampens raw term frequency (log(1+tf) instead of tf) so a document
        # that repeats one word often doesn't dominate every query containing
        # it -- a real risk here, since a document about yoga says "yoga" a lot.
        sublinear_tf=True,
        max_features=6000,
    )
    matrix = vectorizer.fit_transform([c.text for c in kb])
    return vectorizer, matrix


def retrieve(query: str, k: int = 5) -> List[KnowledgeChunk]:
    """The k most relevant knowledge chunks for a question.

    Prefers chunks with a real term overlap, but never returns nothing for an
    on-topic question: if TF-IDF finds no lexical overlap (e.g. the user's
    wording shares no words with any document), it still falls back to the
    top-k chunks so the model has grounding to work from rather than being
    forced to refuse. The system prompt still tells it to say when the
    context genuinely doesn't answer the question.
    """
    kb = _knowledge_base()
    if not kb:
        return []
    vectorizer, matrix = _vectorizer_and_matrix()
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix)[0]
    ranked = sorted(range(len(kb)), key=lambda i: scores[i], reverse=True)
    matched = [kb[i] for i in ranked[:k] if scores[i] > 0]
    if matched:
        return matched
    # No lexical overlap at all -- fall back to the best-ranked chunks so a
    # loosely-worded but on-topic question still gets a grounded answer.
    return [kb[i] for i in ranked[:k]]


SYSTEM_PROMPT = (
    "You are the AyuDrishti yoga assistant -- a warm, knowledgeable yoga "
    "teacher. You help practitioners of every level understand asanas, "
    "breathing (pranayama), meditation, yoga philosophy and safe practice.\n\n"
    "GROUNDING\n"
    "- Base your answer on the CONTEXT provided with the question. It is drawn "
    "from AyuDrishti's asana library and curated knowledge base.\n"
    "- You may connect and explain ideas from the context in your own clear "
    "words -- you do not have to quote it. But do not invent specific facts, "
    "numbers, or claims that contradict it.\n"
    "- If the context genuinely doesn't cover the question, say so briefly and "
    "answer with careful, widely-accepted general yoga knowledge instead of "
    "refusing -- but never fabricate a source or a statistic.\n\n"
    "LINKS AND SOURCES\n"
    "- Only include a web link (research paper, official protocol, dataset) if "
    "that exact URL appears in the context. Never guess or invent a URL.\n"
    "- When the context contains a relevant reference, cite it as a Markdown "
    "link, e.g. [Common Yoga Protocol](https://yoga.ayush.gov.in).\n\n"
    "FORMAT (use Markdown, keep it clean and scannable)\n"
    "- Open with one or two plain sentences that directly answer the question.\n"
    "- Then use **bold** for key terms and short bullet points ('- ') for "
    "steps, benefits, or lists. Use a short '### Heading' only if the answer "
    "has clearly distinct parts.\n"
    "- Be practical and specific. Prefer concrete cues ('stack your knee over "
    "your ankle') over vague ones ('align properly').\n"
    "- Keep it focused -- usually under ~180 words unless the question really "
    "needs more.\n\n"
    "SAFETY\n"
    "- You are not a medical professional. For anything about an injury, "
    "pregnancy, or a medical condition, give general guidance but clearly say "
    "the person should consult a qualified teacher or doctor before acting."
)


async def ask(question: str) -> dict:
    if not settings.groq_api_key:
        raise AssistantUnavailable(
            "The yoga assistant needs a Groq API key. Set GROQ_API_KEY to enable it."
        )

    chunks = retrieve(question, k=5)
    context = (
        "\n\n".join(f"[{c.title}]\n{c.text}" for c in chunks)
        or "No matching context was found in the knowledge base."
    )

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
        ],
        "temperature": 0.4,
        "max_tokens": 900,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.groq_api_base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json=payload,
        )
        if response.status_code >= 400:
            # Groq's own error body says exactly what's wrong (bad key, unknown
            # model, rate limit). Log it so it's diagnosable from the server
            # logs; the client still gets only a generic message.
            logger.error(
                "Groq request failed: model=%s status=%s body=%s",
                settings.groq_model,
                response.status_code,
                response.text[:500],
            )
        response.raise_for_status()

    data = response.json()
    answer = data["choices"][0]["message"]["content"].strip()

    return {
        "answer": answer,
        "sources": [{"id": c.id, "title": c.title, "kind": c.kind} for c in chunks],
    }
