import re
import numpy as np

from rag.document_loader import load_knowledge_base
from rag.embeddings import (
    create_embeddings,
    create_query_embedding
)


STOP_WORDS = {
    "je",
    "su",
    "se",
    "i",
    "u",
    "na",
    "za",
    "od",
    "do",
    "da",
    "šta",
    "sto",
    "koji",
    "koja",
    "koje",
    "kako",
    "između",
    "izmedju",
    "mi",
    "nam"
}


def tokenize(text):

    words = re.findall(
        r"\b\w+\b",
        text.lower(),
        flags=re.UNICODE
    )

    return {
        word
        for word in words
        if len(word) > 2
        and word not in STOP_WORDS
    }


def keyword_similarity(question, text):

    question_words = tokenize(question)

    text_words = tokenize(text)

    if not question_words:
        return 0.0

    common = question_words.intersection(text_words)

    return len(common) / len(question_words)


class PhysicsRetriever:

    def __init__(self, knowledge_base_path):

        self.knowledge_base_path = knowledge_base_path

        self.chunks = load_knowledge_base(
            knowledge_base_path
        )

        if not self.chunks:

            raise ValueError(
                "Nema dokumenata u knowledge base folderu: "
                f"{knowledge_base_path}"
            )

        texts = [
            chunk["text"]
            for chunk in self.chunks
        ]

        self.embeddings = create_embeddings(texts)

    def search(
        self,
        question,
        top_k=4
    ):

        query_embedding = (
            create_query_embedding(question)
        )

        semantic_scores = np.dot(
            self.embeddings,
            query_embedding
        )

        final_scores = []

        for index, chunk in enumerate(self.chunks):

            lexical_score = keyword_similarity(
                question,
                chunk["text"]
            )

            semantic_score = float(
                semantic_scores[index]
            )

            final_score = (
                0.85 * semantic_score
                +
                0.15 * lexical_score
            )

            final_scores.append(final_score)

        best_indices = np.argsort(
            final_scores
        )[::-1][:top_k]

        results = []

        for index in best_indices:

            results.append({
                "text":
                    self.chunks[index]["text"],

                "source":
                    self.chunks[index]["source"],

                "score":
                    float(final_scores[index]),

                "semantic_score":
                    float(semantic_scores[index])
            })

        return results