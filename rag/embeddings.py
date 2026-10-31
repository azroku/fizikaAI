from sentence_transformers import SentenceTransformer


MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


model = SentenceTransformer(MODEL_NAME)


def create_embeddings(texts):

    return model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )


def create_query_embedding(question):

    return model.encode(
        question,
        convert_to_numpy=True,
        normalize_embeddings=True
    )