"""Duplicate-topic detection.

Lightweight TF-IDF + cosine similarity implemented with the standard
library only, tuned for Spanish text (accent folding, stop words and a
naive plural stemmer). It compares a candidate idea against every topic
already in the bank so professors don't publish near-duplicates and
students can check whether their own idea is already taken.
"""
import math
import re
import unicodedata
from collections import Counter

SPANISH_STOPWORDS = {
    "a", "al", "algo", "ante", "antes", "aplicacion", "aplicaciones", "asi", "bajo", "base",
    "cada", "como", "con", "contra", "cual", "cuando", "de", "del", "desde", "donde", "dos",
    "e", "el", "ella", "en", "entre", "es", "esa", "ese", "esta", "este", "esto", "estos",
    "fin", "forma", "ha", "hacia", "hasta", "la", "las", "le", "lo", "los", "mas", "mediante",
    "muy", "ni", "no", "o", "otro", "para", "pero", "por", "proyecto", "que", "se", "segun",
    "ser", "si", "sin", "sistema", "sobre", "son", "su", "sus", "tambien", "tiene", "toda",
    "todo", "tras", "u", "un", "una", "uno", "unos", "uso", "y", "ya", "desarrollo",
    "propuesta", "trabajo", "estudio", "the", "of", "and", "for", "to", "in",
}

# Thresholds used by the business rules.
WARNING_THRESHOLD = 0.35   # show "similar topic" warning
BLOCKING_THRESHOLD = 0.75  # treat as duplicate


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def stem(token: str) -> str:
    """Very small Spanish stemmer: collapses common plural/gender endings."""
    for suffix in ("ciones", "cion", "es", "s", "a", "o"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", normalize(text))
    return [stem(w) for w in words if len(w) > 2 and w not in SPANISH_STOPWORDS]


def _tfidf_vectors(documents: list[list[str]]) -> list[dict[str, float]]:
    doc_count = len(documents)
    document_frequency = Counter(term for doc in documents for term in set(doc))
    vectors = []
    for doc in documents:
        term_counts = Counter(doc)
        total = sum(term_counts.values()) or 1
        vectors.append(
            {
                term: (count / total) * (math.log((1 + doc_count) / (1 + document_frequency[term])) + 1)
                for term, count in term_counts.items()
            }
        )
    return vectors


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    shared = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def topic_text(title: str, description: str, keywords: str = "") -> str:
    # Title and keywords are weighted double: they carry most of the meaning.
    return f"{title} {title} {keywords} {keywords} {description}"


def rank_similar(candidate_text: str, corpus: list[tuple[int, str]], limit: int = 5) -> list[tuple[int, float]]:
    """Return [(item_id, score)] of corpus items most similar to the candidate."""
    if not corpus:
        return []
    documents = [tokenize(candidate_text)] + [tokenize(text) for _, text in corpus]
    vectors = _tfidf_vectors(documents)
    candidate_vector = vectors[0]
    scored = [
        (item_id, round(_cosine(candidate_vector, vector), 3))
        for (item_id, _), vector in zip(corpus, vectors[1:])
    ]
    scored = [item for item in scored if item[1] >= WARNING_THRESHOLD]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]
