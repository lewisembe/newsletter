"""
Category Classifier - Clasificación de titulares usando embeddings
"""

import numpy as np
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter

# Reutilizar Embedder de poc_clustering
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "poc_clustering" / "src"))
from embedder import Embedder, EmbeddingCache


class CategoryClassifier:
    """Clasificador de titulares basado en embeddings semánticos"""

    def __init__(
        self,
        categories_config_path: str,
        embedder: Embedder,
        method: str = "cosine_similarity",
        similarity_threshold: float = 0.5,
        use_examples: bool = True,
        examples_per_category: int = 3,
        category_embedding_strategy: str = "mean",
        categories_to_exclude: Optional[List[str]] = None,
    ):
        """
        Args:
            categories_config_path: Path to categories.yml
            embedder: Instancia de Embedder
            method: Método de clasificación ('cosine_similarity', 'knn', 'threshold')
            similarity_threshold: Umbral mínimo de similitud
            use_examples: Si True, usar ejemplos además de descripción
            examples_per_category: Número de ejemplos por categoría
            category_embedding_strategy: 'mean', 'max', 'weighted_mean'
            categories_to_exclude: Categorías a excluir (ej: ['otros'])
        """
        self.embedder = embedder
        self.method = method
        self.similarity_threshold = similarity_threshold
        self.use_examples = use_examples
        self.examples_per_category = examples_per_category
        self.strategy = category_embedding_strategy
        self.categories_to_exclude = categories_to_exclude or []

        # Cargar categorías
        self.categories = self._load_categories(categories_config_path)

        # Generar embeddings de categorías
        self.category_embeddings = self._generate_category_embeddings()

        print(f"CategoryClassifier initialized with {len(self.categories)} categories")
        print(f"Method: {self.method}, Strategy: {self.strategy}")

    def _load_categories(self, config_path: str) -> Dict:
        """Carga categorías desde categories.yml"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Categories config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        categories = {}
        for cat in config.get("categories", []):
            cat_id = cat["id"]

            # Excluir categorías si especificado
            if cat_id in self.categories_to_exclude:
                continue

            categories[cat_id] = {
                "name": cat["name"],
                "description": cat["description"],
                "examples": cat.get("examples", [])[:self.examples_per_category],
            }

        return categories

    def _generate_category_embeddings(self) -> Dict[str, np.ndarray]:
        """
        Genera embeddings para cada categoría.

        Estrategia:
        - Si use_examples=False: solo descripción
        - Si use_examples=True: descripción + ejemplos

        Returns:
            Dict {categoria_id: embedding_vector}
        """
        print("\nGenerating category embeddings...")
        category_embeddings = {}

        for cat_id, cat_info in self.categories.items():
            texts_to_embed = []

            # Siempre incluir descripción
            texts_to_embed.append(cat_info["description"])

            # Incluir ejemplos si especificado
            if self.use_examples and cat_info["examples"]:
                texts_to_embed.extend(cat_info["examples"])

            # Generar embeddings
            embeddings = self.embedder.embed(texts_to_embed, show_progress=False)

            # Combinar embeddings según estrategia
            if self.strategy == "mean":
                category_embedding = embeddings.mean(axis=0)
            elif self.strategy == "max":
                category_embedding = embeddings.max(axis=0)
            elif self.strategy == "weighted_mean":
                # Dar más peso a la descripción (peso=2) vs ejemplos (peso=1)
                weights = [2.0] + [1.0] * (len(embeddings) - 1)
                weights = np.array(weights) / sum(weights)
                category_embedding = (embeddings.T @ weights).T
            else:
                raise ValueError(f"Unknown strategy: {self.strategy}")

            # Normalizar (importante para cosine similarity)
            category_embedding = category_embedding / np.linalg.norm(category_embedding)

            category_embeddings[cat_id] = category_embedding

            print(f"  {cat_id}: {len(texts_to_embed)} texts → embedding")

        return category_embeddings

    def classify(self, title: str) -> Tuple[str, float]:
        """
        Clasifica un titular.

        Args:
            title: Titular a clasificar

        Returns:
            (categoria_id, confidence_score)
        """
        # Generar embedding del titular
        title_embedding = self.embedder.embed_single(title)

        # Calcular similitud con cada categoría
        similarities = {}
        for cat_id, cat_embedding in self.category_embeddings.items():
            # Cosine similarity (vectores ya normalizados)
            similarity = np.dot(title_embedding, cat_embedding)
            similarities[cat_id] = similarity

        # Ordenar por similitud
        sorted_cats = sorted(similarities.items(), key=lambda x: x[1], reverse=True)

        # Mejor categoría
        best_cat, best_score = sorted_cats[0]

        # Aplicar threshold
        if self.method == "threshold" and best_score < self.similarity_threshold:
            return "otros", best_score

        return best_cat, best_score

    def classify_batch(
        self,
        titles: List[str],
        show_progress: bool = True,
    ) -> List[Tuple[str, float]]:
        """
        Clasifica múltiples titulares.

        Args:
            titles: Lista de titulares
            show_progress: Mostrar barra de progreso

        Returns:
            Lista de (categoria_id, confidence_score)
        """
        # Generar embeddings de todos los titulares
        title_embeddings = self.embedder.embed(titles, show_progress=show_progress)

        # Clasificar cada titular
        results = []
        for title_emb in title_embeddings:
            # Calcular similitud con cada categoría
            similarities = {}
            for cat_id, cat_embedding in self.category_embeddings.items():
                similarity = np.dot(title_emb, cat_embedding)
                similarities[cat_id] = similarity

            # Mejor categoría
            sorted_cats = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
            best_cat, best_score = sorted_cats[0]

            # Aplicar threshold
            if self.method == "threshold" and best_score < self.similarity_threshold:
                results.append(("otros", best_score))
            else:
                results.append((best_cat, best_score))

        return results

    def get_all_similarities(self, title: str) -> Dict[str, float]:
        """
        Obtiene similitud con todas las categorías para un titular.

        Args:
            title: Titular

        Returns:
            Dict {categoria_id: similarity_score}
        """
        title_embedding = self.embedder.embed_single(title)

        similarities = {}
        for cat_id, cat_embedding in self.category_embeddings.items():
            similarity = np.dot(title_embedding, cat_embedding)
            similarities[cat_id] = similarity

        return similarities

    def get_category_info(self, cat_id: str) -> Optional[Dict]:
        """Obtiene información de una categoría"""
        return self.categories.get(cat_id)

    def get_available_categories(self) -> List[str]:
        """Lista de categorías disponibles"""
        return list(self.categories.keys())


if __name__ == "__main__":
    # Test
    print("Testing CategoryClassifier...")

    # Inicializar embedder
    embedder = Embedder(
        model_name="intfloat/multilingual-e5-small",
        cache_dir="../poc_clustering/models_cache",
        device="cpu",
        batch_size=32,
    )

    # Inicializar classifier
    classifier = CategoryClassifier(
        categories_config_path="../config/categories.yml",
        embedder=embedder,
        method="cosine_similarity",
        similarity_threshold=0.5,
        use_examples=True,
        examples_per_category=3,
        category_embedding_strategy="mean",
        categories_to_exclude=["otros"],
    )

    # Test con titulares
    test_titles = [
        "Sánchez anuncia nueva reforma fiscal para 2026",  # economia/politica
        "Banco Central sube tipos de interés al 4.5%",  # economia
        "Apple lanza nuevo iPhone 16 con IA integrada",  # tecnologia
        "El Madrid gana la Champions League",  # deportes
        "Conflicto en Oriente Medio escala a nueva fase",  # geopolitica
        "Museo del Prado inaugura exposición de Velázquez",  # sociedad/cultura
        "Goldman Sachs reporta ganancias récord en Q3",  # finanzas
    ]

    print("\n=== Testing classification ===")
    for title in test_titles:
        cat, score = classifier.classify(title)
        print(f"\n'{title}'")
        print(f"  → {cat} (score: {score:.3f})")

        # Mostrar todas las similitudes
        all_sims = classifier.get_all_similarities(title)
        print(f"  All similarities:")
        for cat_id, sim in sorted(all_sims.items(), key=lambda x: x[1], reverse=True):
            print(f"    {cat_id}: {sim:.3f}")

    # Test batch classification
    print("\n=== Testing batch classification ===")
    results = classifier.classify_batch(test_titles, show_progress=True)
    for title, (cat, score) in zip(test_titles, results):
        print(f"{cat:12} ({score:.3f}) | {title[:60]}")
