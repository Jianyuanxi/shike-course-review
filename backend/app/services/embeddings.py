from functools import cached_property

from app.config import settings


class LocalEmbedder:
    dimension = 512

    def __init__(self) -> None:
        self.model_name = settings.embedding_model

    @cached_property
    def _model(self):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.model_name, device=settings.embedding_device)

    def __call__(self, input):
        texts = [input] if isinstance(input, str) else list(input)
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def encode_query(self, query: str) -> list[float]:
        instruction = "为这个句子生成表示以用于检索相关文章："
        return self([instruction + query])[0]
