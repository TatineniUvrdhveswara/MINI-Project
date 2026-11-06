from collections.abc import Sequence

from ..config import get_settings


class EmbeddingProvider:
    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.device = device or settings.embedding_device
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self._load().encode(list(texts), normalize_embeddings=True)
        return embeddings.tolist()


embedding_provider = EmbeddingProvider()
