from feature_achievement.enrichment import load_all_enriched_data

# from feature_achievement.index import build_keyphrases_index
from feature_achievement.legacy.edge_generation2 import (
    generate_edges,
    collect_chapter_texts,
    build_tfidf_index,
)
from feature_achievement.tfidf_debug import print_top_k_similar_chapters

enriched_books = load_all_enriched_data("book_content/books.yaml")
# index = build_keyphrases_index(enriched_books)
edges = generate_edges(enriched_books)
print(len(edges))
print(edges)
# print(enriched_books)

# chapter_texts = collect_chapter_texts(enriched_books)
# tfidf_index = build_tfidf_index(chapter_texts)
# print_top_k_similar_chapters(
#     "spring-start-here::ch5",
#     tfidf_index,
#     enriched_books,
# )

