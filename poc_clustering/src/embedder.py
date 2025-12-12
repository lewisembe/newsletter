"""
Embedder - Generación de embeddings semánticos para titulares
"""

import numpy as np
from pathlib import Path
from typing import List
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


class Embedder:
    """Genera embeddings para titulares usando sentence-transformers"""

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        cache_dir: str = "./models_cache",
        device: str = "cpu",
        batch_size: int = 100,
    ):
        """
        Args:
            model_name: Nombre del modelo en HuggingFace
            cache_dir: Directorio para cachear el modelo
            device: 'cpu' o 'cuda'
            batch_size: Tamaño de batch para procesamiento
        """
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.device = device
        self.batch_size = batch_size

        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(
            model_name, cache_folder=str(self.cache_dir), device=device
        )
        print(f"Model loaded. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")

    def embed(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """
        Genera embeddings para una lista de textos.

        Args:
            texts: Lista de textos (titulares)
            show_progress: Mostrar barra de progreso

        Returns:
            Array numpy de shape (len(texts), embedding_dim)
        """
        if not texts:
            return np.array([])

        # Para multilingual-e5, se recomienda prefijo "query: " para búsqueda
        # pero como estamos haciendo clustering (comparación texto-texto),
        # usamos "passage: " o ningún prefijo
        # Ref: https://huggingface.co/intfloat/multilingual-e5-small

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Normalizar para cosine similarity
        )

        return embeddings

    def embed_single(self, text: str) -> np.ndarray:
        """
        Genera embedding para un solo texto.

        Args:
            text: Texto (titular)

        Returns:
            Array numpy de shape (embedding_dim,)
        """
        embedding = self.model.encode(
            text, convert_to_numpy=True, normalize_embeddings=True
        )
        return embedding

    def get_embedding_dim(self) -> int:
        """Retorna la dimensión de los embeddings"""
        return self.model.get_sentence_embedding_dimension()


class EmbeddingCache:
    """Cache para evitar re-calcular embeddings de los mismos textos"""

    def __init__(self):
        self.cache = {}  # text -> embedding

    def get(self, text: str) -> np.ndarray:
        """Obtiene embedding del cache"""
        return self.cache.get(text)

    def set(self, text: str, embedding: np.ndarray):
        """Guarda embedding en cache"""
        self.cache[text] = embedding

    def get_or_compute(
        self, text: str, embedder: Embedder
    ) -> np.ndarray:
        """Obtiene del cache o calcula si no existe"""
        embedding = self.get(text)
        if embedding is None:
            embedding = embedder.embed_single(text)
            self.set(text, embedding)
        return embedding

    def size(self) -> int:
        """Número de embeddings en cache"""
        return len(self.cache)

    def clear(self):
        """Limpia el cache"""
        self.cache.clear()


if __name__ == "__main__":
    # Test
    print("Testing Embedder...")

    embedder = Embedder(
        model_name="intfloat/multilingual-e5-small",
        cache_dir="./test_models_cache",
        device="cpu",
        batch_size=32,
    )

    # Test con titulares de ejemplo
    test_titles = [
        "Sánchez anuncia nueva reforma fiscal para 2026",
        "El Gobierno presenta su plan de reforma tributaria",
        "Apple lanza nuevo iPhone 16 con IA integrada",
        "Microsoft adquiere startup de inteligencia artificial",
        "El Madrid gana la Champions League por decimoquinta vez",
    ]

    print(f"\nGenerating embeddings for {len(test_titles)} test titles...")
    embeddings = embedder.embed(test_titles)

    print(f"Embeddings shape: {embeddings.shape}")
    print(f"Expected: ({len(test_titles)}, {embedder.get_embedding_dim()})")

    # Test similitud coseno
    from numpy.linalg import norm

    def cosine_similarity(a, b):
        return np.dot(a, b) / (norm(a) * norm(b))

    print("\nCosine similarities:")
    print(f"Fiscal 1 vs Fiscal 2: {cosine_similarity(embeddings[0], embeddings[1]):.3f}")
    print(f"Fiscal 1 vs Apple: {cosine_similarity(embeddings[0], embeddings[2]):.3f}")
    print(f"Apple vs Microsoft: {cosine_similarity(embeddings[2], embeddings[3]):.3f}")

    # Test cache
    print("\nTesting EmbeddingCache...")
    cache = EmbeddingCache()
    cache.set(test_titles[0], embeddings[0])
    cached_emb = cache.get(test_titles[0])
    print(f"Cache working: {np.allclose(cached_emb, embeddings[0])}")
    print(f"Cache size: {cache.size()}")
