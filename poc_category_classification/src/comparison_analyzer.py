"""
Comparison Analyzer - Análisis y comparación de métodos de clasificación
LLM (ground truth) vs Embeddings
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)


class ComparisonAnalyzer:
    """Analiza y compara resultados de clasificación LLM vs Embeddings"""

    def __init__(self):
        self.results = []  # (url_id, title, llm_category, embedding_category, confidence)
        self.categories = set()

    def add_result(
        self,
        url_id: int,
        title: str,
        llm_category: str,
        embedding_category: str,
        confidence: float,
    ):
        """
        Añade un resultado de clasificación.

        Args:
            url_id: ID de la URL
            title: Titular
            llm_category: Categoría asignada por LLM (ground truth)
            embedding_category: Categoría predicha por embeddings
            confidence: Confianza de la predicción (similarity score)
        """
        self.results.append({
            "url_id": url_id,
            "title": title,
            "llm": llm_category,
            "embedding": embedding_category,
            "confidence": confidence,
            "correct": llm_category == embedding_category,
        })
        self.categories.add(llm_category)
        self.categories.add(embedding_category)

    def get_metrics(self) -> Dict:
        """
        Calcula métricas globales de clasificación.

        Returns:
            Dict con accuracy, precision, recall, f1
        """
        if not self.results:
            return {}

        y_true = [r["llm"] for r in self.results]
        y_pred = [r["embedding"] for r in self.results]

        # Métricas globales
        accuracy = accuracy_score(y_true, y_pred)

        # Precision, Recall, F1 (macro average)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true, y_pred, average="macro", zero_division=0
        )

        # Weighted average (ponderado por frecuencia de clase)
        precision_w, recall_w, f1_w, _ = precision_recall_fscore_support(
            y_true, y_pred, average="weighted", zero_division=0
        )

        return {
            "accuracy": accuracy,
            "precision_macro": precision,
            "recall_macro": recall,
            "f1_macro": f1,
            "precision_weighted": precision_w,
            "recall_weighted": recall_w,
            "f1_weighted": f1_w,
            "total_samples": len(self.results),
        }

    def get_per_category_metrics(self) -> Dict[str, Dict]:
        """
        Calcula métricas por categoría.

        Returns:
            Dict {categoria: {precision, recall, f1, support}}
        """
        if not self.results:
            return {}

        y_true = [r["llm"] for r in self.results]
        y_pred = [r["embedding"] for r in self.results]

        # Todas las categorías
        categories = sorted(self.categories)

        # Precision, Recall, F1 por categoría
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true, y_pred, labels=categories, zero_division=0
        )

        metrics = {}
        for i, cat in enumerate(categories):
            metrics[cat] = {
                "precision": precision[i],
                "recall": recall[i],
                "f1": f1[i],
                "support": int(support[i]),
            }

        return metrics

    def get_confusion_matrix(self) -> Tuple[np.ndarray, List[str]]:
        """
        Genera matriz de confusión.

        Returns:
            (confusion_matrix, labels)
        """
        if not self.results:
            return np.array([]), []

        y_true = [r["llm"] for r in self.results]
        y_pred = [r["embedding"] for r in self.results]

        categories = sorted(self.categories)
        cm = confusion_matrix(y_true, y_pred, labels=categories)

        return cm, categories

    def get_error_analysis(
        self, max_examples_per_error: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        Analiza errores de clasificación.

        Args:
            max_examples_per_error: Máximo de ejemplos por tipo de error

        Returns:
            Dict con ejemplos de errores agrupados por (llm_cat, embedding_cat)
        """
        errors = defaultdict(list)

        for r in self.results:
            if not r["correct"]:
                key = f"{r['llm']} → {r['embedding']}"
                errors[key].append({
                    "url_id": r["url_id"],
                    "title": r["title"],
                    "confidence": r["confidence"],
                })

        # Limitar ejemplos por tipo de error
        for key in errors:
            # Ordenar por confianza (errores con alta confianza son más interesantes)
            errors[key] = sorted(
                errors[key], key=lambda x: x["confidence"], reverse=True
            )[:max_examples_per_error]

        return dict(errors)

    def get_confusion_patterns(self) -> List[Tuple[str, str, int]]:
        """
        Analiza patrones de confusión entre categorías.

        Returns:
            Lista de (llm_cat, embedding_cat, count) ordenada por frecuencia
        """
        confusion_counts = Counter()

        for r in self.results:
            if not r["correct"]:
                confusion_counts[(r["llm"], r["embedding"])] += 1

        # Ordenar por frecuencia
        return sorted(
            [(llm, emb, count) for (llm, emb), count in confusion_counts.items()],
            key=lambda x: x[2],
            reverse=True,
        )

    def get_confidence_stats(self) -> Dict:
        """
        Estadísticas de confianza (similarity scores).

        Returns:
            Dict con media, mediana, percentiles para correctos/incorrectos
        """
        correct_confidences = [r["confidence"] for r in self.results if r["correct"]]
        incorrect_confidences = [r["confidence"] for r in self.results if not r["correct"]]

        def stats(values):
            if not values:
                return {}
            return {
                "mean": np.mean(values),
                "median": np.median(values),
                "std": np.std(values),
                "min": np.min(values),
                "max": np.max(values),
                "p25": np.percentile(values, 25),
                "p75": np.percentile(values, 75),
            }

        return {
            "correct": stats(correct_confidences),
            "incorrect": stats(incorrect_confidences),
            "all": stats([r["confidence"] for r in self.results]),
        }

    def get_classification_report(self) -> str:
        """
        Genera reporte de clasificación (sklearn).

        Returns:
            String con reporte formateado
        """
        if not self.results:
            return ""

        y_true = [r["llm"] for r in self.results]
        y_pred = [r["embedding"] for r in self.results]

        return classification_report(y_true, y_pred, zero_division=0)

    def export_to_csv(self, output_path: str):
        """
        Exporta resultados a CSV.

        Args:
            output_path: Ruta del archivo CSV
        """
        import csv

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "url_id",
                    "title",
                    "llm_category",
                    "embedding_category",
                    "confidence",
                    "correct",
                ],
            )
            writer.writeheader()
            for r in self.results:
                writer.writerow({
                    "url_id": r["url_id"],
                    "title": r["title"],
                    "llm_category": r["llm"],
                    "embedding_category": r["embedding"],
                    "confidence": r["confidence"],
                    "correct": r["correct"],
                })

    def get_summary(self) -> str:
        """
        Genera resumen textual de resultados.

        Returns:
            String con resumen formateado
        """
        metrics = self.get_metrics()

        if not metrics:
            return "No results to analyze."

        total = metrics["total_samples"]
        correct = sum(1 for r in self.results if r["correct"])
        incorrect = total - correct

        summary = []
        summary.append(f"Total samples: {total}")
        summary.append(f"Correct: {correct} ({correct/total*100:.1f}%)")
        summary.append(f"Incorrect: {incorrect} ({incorrect/total*100:.1f}%)")
        summary.append(f"\nOverall Metrics:")
        summary.append(f"  Accuracy: {metrics['accuracy']:.3f}")
        summary.append(f"  Precision (macro): {metrics['precision_macro']:.3f}")
        summary.append(f"  Recall (macro): {metrics['recall_macro']:.3f}")
        summary.append(f"  F1 (macro): {metrics['f1_macro']:.3f}")

        return "\n".join(summary)


if __name__ == "__main__":
    # Test
    print("Testing ComparisonAnalyzer...")

    analyzer = ComparisonAnalyzer()

    # Simular resultados
    test_data = [
        (1, "Gobierno anuncia reforma", "politica", "politica", 0.85),
        (2, "Banco Central sube tipos", "economia", "economia", 0.92),
        (3, "Apple lanza iPhone", "tecnologia", "tecnologia", 0.88),
        (4, "Madrid gana Champions", "deportes", "deportes", 0.95),
        (5, "Artículo sobre fiscalidad", "economia", "politica", 0.67),  # Error
        (6, "Startup recibe inversión", "finanzas", "tecnologia", 0.72),  # Error
    ]

    for url_id, title, llm_cat, emb_cat, conf in test_data:
        analyzer.add_result(url_id, title, llm_cat, emb_cat, conf)

    # Métricas globales
    print("\n=== Metrics ===")
    metrics = analyzer.get_metrics()
    for key, value in metrics.items():
        print(f"{key}: {value}")

    # Métricas por categoría
    print("\n=== Per-Category Metrics ===")
    per_cat = analyzer.get_per_category_metrics()
    for cat, cat_metrics in per_cat.items():
        print(f"\n{cat}:")
        for metric, value in cat_metrics.items():
            print(f"  {metric}: {value}")

    # Confusion matrix
    print("\n=== Confusion Matrix ===")
    cm, labels = analyzer.get_confusion_matrix()
    print(f"Labels: {labels}")
    print(cm)

    # Error analysis
    print("\n=== Error Analysis ===")
    errors = analyzer.get_error_analysis(max_examples_per_error=3)
    for error_type, examples in errors.items():
        print(f"\n{error_type}:")
        for ex in examples:
            print(f"  - {ex['title']} (conf: {ex['confidence']:.3f})")

    # Confidence stats
    print("\n=== Confidence Stats ===")
    conf_stats = analyzer.get_confidence_stats()
    for category, stats in conf_stats.items():
        print(f"\n{category}:")
        for stat, value in stats.items():
            print(f"  {stat}: {value:.3f}")

    # Summary
    print("\n=== Summary ===")
    print(analyzer.get_summary())
