from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# =====================================================
# 1) Data Collection
# =====================================================


def collect_chapter_texts(enriched_books):
    """
    Return:
        dict[chapter_id] -> chapter_text (str)
    """
    texts = {}
    for book in enriched_books:
        for chapter in book["chapters"]:
            texts[chapter["id"]] = chapter.get("chapter_text", "")
    return texts


def get_book_id(chapter_id: str) -> str:
    """spring-in-action::ch1->{book_id}::{chapter_id}"""
    return chapter_id.split("::")[0]


# =====================================================
# 2) TF-IDF Index
# =====================================================


def build_tfidf_index(chapter_texts: dict):
    """
    Input:
        chapter_texts: dict[chapter_id] -> text
    Output:
        {
            "chapter_ids": [...],
            "tfidf_matrix": scipy sparse matrix,
            "vectorizer": TfidfVectorizer
        }
    """
    chapter_ids = list(chapter_texts.keys())
    corpus = [chapter_texts[cid] or "" for cid in chapter_ids]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
        min_df=1,  # debug-friendly
    )

    tfidf_matrix = vectorizer.fit_transform(corpus)

    return {
        "chapter_ids": chapter_ids,
        "tfidf_matrix": tfidf_matrix,
        "vectorizer": vectorizer,
    }


def tfidf_similarity(src_id, tgt_id, tfidf_index) -> float:
    chapter_ids = tfidf_index["chapter_ids"]
    tfidf_matrix = tfidf_index["tfidf_matrix"]

    i = chapter_ids.index(src_id)
    j = chapter_ids.index(tgt_id)

    return float(cosine_similarity(tfidf_matrix[i], tfidf_matrix[j])[0][0])


# =====================================================
# 3) Candidate Generation (TF-IDF top tokens)
# =====================================================


def extract_top_tfidf_tokens(tfidf_index, top_n=20):
    """
    Return:
        dict[chapter_id] -> list[str] (top tf-idf tokens)
    """
    chapter_ids = tfidf_index["chapter_ids"]
    tfidf_matrix = tfidf_index["tfidf_matrix"]
    feature_names = tfidf_index["vectorizer"].get_feature_names_out()

    chapter_top_tokens = {}

    for idx, chapter_id in enumerate(chapter_ids):
        row = tfidf_matrix[idx].toarray().ravel()
        if row.sum() == 0:
            chapter_top_tokens[chapter_id] = []
            continue

        top_indices = np.argsort(row)[-top_n:]
        tokens = [feature_names[i] for i in top_indices if row[i] > 0]

        chapter_top_tokens[chapter_id] = tokens

    return chapter_top_tokens


def build_token_index(chapter_top_tokens):
    """
    token -> set(chapter_id)
    """
    index = defaultdict(set)
    for cid, tokens in chapter_top_tokens.items():
        for t in tokens:
            index[t].add(cid)
    return index


def generate_candidates(
    src_id,
    chapter_top_tokens,
    token_index,
    min_shared_tokens=2,
):
    """
    Candidate v1:
    - TF-IDF token recall
    - shared-token >= k
    """
    overlap = defaultdict(int)

    for token in chapter_top_tokens.get(src_id, []):
        for tgt_id in token_index.get(token, []):
            if tgt_id != src_id:
                overlap[tgt_id] += 1

    return {tgt_id for tgt_id, cnt in overlap.items() if cnt >= min_shared_tokens}


# =====================================================
# 4) Edge Generation
# =====================================================


def generate_edges(
    enriched_books,
    min_shared_tokens=2,
    min_tfidf_score=0.1,
):
    edges = []

    chapter_texts = collect_chapter_texts(enriched_books)
    tfidf_index = build_tfidf_index(chapter_texts)

    chapter_top_tokens = extract_top_tfidf_tokens(tfidf_index)
    token_index = build_token_index(chapter_top_tokens)

    for book in enriched_books:
        for chapter in book["chapters"]:
            src_id = chapter["id"]
            src_book = get_book_id(src_id)
            candidates = generate_candidates(
                src_id,
                chapter_top_tokens,
                token_index,
                min_shared_tokens=min_shared_tokens,
            )

            for tgt_id in candidates:
                tgt_book = get_book_id(tgt_id)

                if src_book == tgt_book:
                    continue

                score = tfidf_similarity(src_id, tgt_id, tfidf_index)

                if score < min_tfidf_score:
                    continue

                edges.append(
                    {
                        "from": src_id,
                        "to": tgt_id,
                        "type": "tfidf_similarity",
                        "score": score,
                    }
                )

    return edges

