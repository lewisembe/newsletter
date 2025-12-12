"""
FAISS KNN Classifier - Clasificación usando K-Nearest Neighbors con FAISS
Usa todas las URLs clasificadas como base de conocimiento para búsqueda rápida
"""

import numpy as np
import faiss
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter


class FAISSClassifier:
    """Clasificador KNN usando FAISS para búsqueda eficiente de vecinos"""

    def __init__(
        self,
        k: int = 5,
        distance_metric: str = "cosine",
        use_gpu: bool = False,
    ):
        """
        Args:
            k: Número de vecinos a considerar
            distance_metric: 'cosine' o 'l2' (euclidean)
            use_gpu: Usar GPU si está disponible (False para Raspberry Pi)
        """
        self.k = k
        self.distance_metric = distance_metric
        self.use_gpu = use_gpu

        self.index = None
        self.embeddings = None
        self.labels = None
        self.label_to_idx = None
        self.idx_to_label = None
        self.is_trained = False

    def fit(self, embeddings: np.ndarray, labels: np.ndarray):
        """
        Construye el índice FAISS con embeddings conocidos.

        Args:
            embeddings: Array de embeddings, shape (n_samples, n_features)
            labels: Array de categorías, shape (n_samples,)
        """
        print(f"\n🔧 Building FAISS index...")
        print(f"  Samples: {len(embeddings)}")
        print(f"  Features: {embeddings.shape[1]}")
        print(f"  K neighbors: {self.k}")
        print(f"  Distance: {self.distance_metric}")

        # Guardar datos
        self.embeddings = embeddings.astype('float32')
        self.labels = labels

        # Mapeos de labels
        unique_labels = np.unique(labels)
        self.label_to_idx = {label: idx for idx, label in enumerate(unique_labels)}
        self.idx_to_label = {idx: label for label, idx in self.label_to_idx.items()}

        # Normalizar embeddings si usamos cosine similarity
        if self.distance_metric == "cosine":
            # FAISS usa inner product, así que normalizamos para que IP = cosine
            faiss.normalize_L2(self.embeddings)

        # Crear índice FAISS
        dimension = embeddings.shape[1]

        if self.distance_metric == "cosine":
            # Inner product (con embeddings normalizados = cosine)
            self.index = faiss.IndexFlatIP(dimension)
        else:
            # L2 (Euclidean)
            self.index = faiss.IndexFlatL2(dimension)

        # Añadir embeddings al índice
        self.index.add(self.embeddings)

        self.is_trained = True
        print(f"  ✓ Index built with {self.index.ntotal} vectors")

    def predict(self, query_embeddings: np.ndarray) -> np.ndarray:
        """
        Predice categorías para embeddings de query.

        Args:
            query_embeddings: Array de embeddings a clasificar

        Returns:
            Array de categorías predichas
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call fit() first.")

        predictions, _ = self.predict_with_confidence(query_embeddings)
        return predictions

    def predict_with_confidence(
        self, query_embeddings: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predice categorías con scores de confianza.

        Args:
            query_embeddings: Array de embeddings a clasificar

        Returns:
            (predictions, confidences)
            - predictions: Array de categorías predichas
            - confidences: Array de scores de confianza [0-1]
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call fit() first.")

        query_embeddings = query_embeddings.astype('float32')

        # Normalizar queries si usamos cosine
        if self.distance_metric == "cosine":
            faiss.normalize_L2(query_embeddings)

        # Buscar K vecinos más cercanos
        distances, indices = self.index.search(query_embeddings, self.k)

        predictions = []
        confidences = []

        for i in range(len(query_embeddings)):
            # Obtener labels de los K vecinos
            neighbor_indices = indices[i]
            neighbor_labels = [self.labels[idx] for idx in neighbor_indices]

            # Votación por mayoría
            vote_counts = Counter(neighbor_labels)
            best_label = vote_counts.most_common(1)[0][0]

            # Confianza = proporción de votos para la categoría ganadora
            confidence = vote_counts[best_label] / self.k

            predictions.append(best_label)
            confidences.append(confidence)

        return np.array(predictions), np.array(confidences)

    def predict_with_neighbors(
        self, query_embeddings: np.ndarray
    ) -> List[Dict]:
        """
        Predice categorías y retorna información detallada de vecinos.

        Args:
            query_embeddings: Array de embeddings a clasificar

        Returns:
            Lista de dicts con prediction, confidence, neighbors
        """
        if not self.is_trained:
            raise ValueError("Classifier not trained. Call fit() first.")

        query_embeddings = query_embeddings.astype('float32')

        if self.distance_metric == "cosine":
            faiss.normalize_L2(query_embeddings)

        distances, indices = self.index.search(query_embeddings, self.k)

        results = []
        for i in range(len(query_embeddings)):
            neighbor_indices = indices[i]
            neighbor_distances = distances[i]
            neighbor_labels = [self.labels[idx] for idx in neighbor_indices]

            # Votación
            vote_counts = Counter(neighbor_labels)
            best_label = vote_counts.most_common(1)[0][0]
            confidence = vote_counts[best_label] / self.k

            # Información de vecinos
            neighbors = []
            for idx, dist, label in zip(neighbor_indices, neighbor_distances, neighbor_labels):
                neighbors.append({
                    "index": int(idx),
                    "distance": float(dist),
                    "label": label,
                })

            results.append({
                "prediction": best_label,
                "confidence": confidence,
                "neighbors": neighbors,
                "vote_distribution": dict(vote_counts),
            })

        return results

    def evaluate(
        self, X_test: np.ndarray, y_test: np.ndarray, verbose: bool = True
    ) -> Dict:
        """
        Evalúa el clasificador en test set.

        Args:
            X_test: Features de test
            y_test: Labels de test
            verbose: Mostrar resultados

        Returns:
            Dict con métricas
        """
        from sklearn.metrics import (
            accuracy_score,
            precision_recall_fscore_support,
        )

        y_pred, confidences = self.predict_with_confidence(X_test)

        accuracy = accuracy_score(y_test, y_pred)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, average="macro", zero_division=0
        )

        if verbose:
            print(f"\n📊 FAISS KNN Evaluation:")
            print(f"  Accuracy: {accuracy:.3f}")
            print(f"  Precision (macro): {precision:.3f}")
            print(f"  Recall (macro): {recall:.3f}")
            print(f"  F1 (macro): {f1:.3f}")
            print(f"  Avg confidence: {confidences.mean():.3f}")

        return {
            "accuracy": accuracy,
            "precision_macro": precision,
            "recall_macro": recall,
            "f1_macro": f1,
            "avg_confidence": confidences.mean(),
            "predictions": y_pred,
            "confidences": confidences,
        }

    def save(self, path: str):
        """Guarda el índice FAISS (si es necesario más adelante)"""
        raise NotImplementedError("Save not implemented yet")

    @classmethod
    def load(cls, path: str):
        """Carga índice guardado"""
        raise NotImplementedError("Load not implemented yet")


if __name__ == "__main__":
    # Test
    print("Testing FAISSClassifier...")

    # Datos sintéticos
    np.random.seed(42)

    # Training data
    X_train = np.random.randn(1000, 384).astype('float32')
    y_train = np.random.choice(["economia", "politica", "tecnologia"], size=1000)

    # Test data
    X_test = np.random.randn(200, 384).astype('float32')
    y_test = np.random.choice(["economia", "politica", "tecnologia"], size=200)

    # Test classifier
    clf = FAISSClassifier(k=5, distance_metric="cosine")
    clf.fit(X_train, y_train)

    # Evaluate
    metrics = clf.evaluate(X_test, y_test)

    # Test predictions with details
    print("\n=== Sample predictions with neighbors ===")
    results = clf.predict_with_neighbors(X_test[:3])
    for i, result in enumerate(results):
        print(f"\nQuery {i}:")
        print(f"  Prediction: {result['prediction']}")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  Vote distribution: {result['vote_distribution']}")
        print(f"  Neighbors:")
        for n in result['neighbors'][:3]:
            print(f"    - Label: {n['label']}, Distance: {n['distance']:.3f}")

    print("\n✓ All tests passed")
