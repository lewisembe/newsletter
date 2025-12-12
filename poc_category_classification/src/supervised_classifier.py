"""
Supervised Classifier - Clasificación supervisada sobre embeddings
Entrena clasificadores tradicionales (LR, XGBoost, RF) usando embeddings como features
"""

import numpy as np
import joblib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix,
)

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("Warning: XGBoost not installed. Install with: pip install xgboost")


class SupervisedClassifier:
    """Clasificador supervisado entrenado sobre embeddings"""

    AVAILABLE_MODELS = {
        "logistic_regression": {
            "class": LogisticRegression,
            "params": {
                "max_iter": 1000,
                "class_weight": "balanced",
                "random_state": 42,
                "solver": "lbfgs",
                "multi_class": "multinomial",
            },
            "description": "Logistic Regression (fast, interpretable)",
        },
        "random_forest": {
            "class": RandomForestClassifier,
            "params": {
                "n_estimators": 100,
                "max_depth": 20,
                "class_weight": "balanced",
                "random_state": 42,
                "n_jobs": -1,
            },
            "description": "Random Forest (ensemble, robust)",
        },
    }

    # XGBoost agregado condicionalmente
    if HAS_XGBOOST:
        AVAILABLE_MODELS["xgboost"] = {
            "class": XGBClassifier,
            "params": {
                "n_estimators": 100,
                "max_depth": 6,
                "learning_rate": 0.1,
                "random_state": 42,
                "eval_metric": "mlogloss",
                "use_label_encoder": False,
            },
            "description": "XGBoost (high accuracy, gradient boosting)",
        }

    def __init__(self, model_type: str = "logistic_regression"):
        """
        Args:
            model_type: Tipo de modelo ('logistic_regression', 'xgboost', 'random_forest')
        """
        if model_type not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Unknown model type: {model_type}. "
                f"Available: {list(self.AVAILABLE_MODELS.keys())}"
            )

        self.model_type = model_type
        model_config = self.AVAILABLE_MODELS[model_type]

        self.model = model_config["class"](**model_config["params"])
        self.label_encoder = LabelEncoder()
        self.classes_ = None
        self.is_trained = False

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        cv_folds: int = 5,
        verbose: bool = True,
    ) -> Dict:
        """
        Entrena el clasificador con cross-validation.

        Args:
            X_train: Features (embeddings), shape (n_samples, n_features)
            y_train: Labels (categorías), shape (n_samples,)
            cv_folds: Número de folds para cross-validation
            verbose: Mostrar progreso

        Returns:
            Dict con métricas de cross-validation
        """
        if verbose:
            print(f"\nTraining {self.model_type}...")
            print(f"  Training samples: {len(X_train)}")
            print(f"  Features: {X_train.shape[1]}")
            print(f"  Classes: {len(np.unique(y_train))}")

        # Encode labels (for XGBoost compatibility)
        y_train_encoded = self.label_encoder.fit_transform(y_train)
        self.classes_ = self.label_encoder.classes_

        # Cross-validation
        if cv_folds > 1:
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
            cv_scores = cross_val_score(
                self.model, X_train, y_train_encoded, cv=cv, scoring="accuracy", n_jobs=-1
            )

            if verbose:
                print(f"\n  Cross-validation ({cv_folds} folds):")
                print(f"    Accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
                print(f"    Scores: {cv_scores}")
        else:
            cv_scores = []

        # Train on full dataset
        self.model.fit(X_train, y_train_encoded)
        self.is_trained = True

        if verbose:
            print(f"  ✓ Training completed")

        return {
            "cv_mean": cv_scores.mean() if len(cv_scores) > 0 else None,
            "cv_std": cv_scores.std() if len(cv_scores) > 0 else None,
            "cv_scores": cv_scores.tolist() if len(cv_scores) > 0 else [],
        }

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
            Dict con métricas de evaluación
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        # Encode test labels
        y_test_encoded = self.label_encoder.transform(y_test)

        # Predictions (encoded)
        y_pred_encoded = self.model.predict(X_test)

        # Decode predictions back to original labels
        y_pred = self.label_encoder.inverse_transform(y_pred_encoded)

        # Metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, average="macro", zero_division=0
        )

        precision_w, recall_w, f1_w, _ = precision_recall_fscore_support(
            y_test, y_pred, average="weighted", zero_division=0
        )

        if verbose:
            print(f"\n  Test Set Evaluation:")
            print(f"    Accuracy: {accuracy:.3f}")
            print(f"    Precision (macro): {precision:.3f}")
            print(f"    Recall (macro): {recall:.3f}")
            print(f"    F1 (macro): {f1:.3f}")

        return {
            "accuracy": accuracy,
            "precision_macro": precision,
            "recall_macro": recall,
            "f1_macro": f1,
            "precision_weighted": precision_w,
            "recall_weighted": recall_w,
            "f1_weighted": f1_w,
            "predictions": y_pred,
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predice categorías para nuevos samples.

        Args:
            X: Features (embeddings)

        Returns:
            Array de categorías predichas
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        y_pred_encoded = self.model.predict(X)
        return self.label_encoder.inverse_transform(y_pred_encoded)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predice probabilidades para cada clase.

        Args:
            X: Features (embeddings)

        Returns:
            Array de probabilidades, shape (n_samples, n_classes)
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        return self.model.predict_proba(X)

    def predict_with_confidence(
        self, X: np.ndarray
    ) -> List[Tuple[str, float]]:
        """
        Predice categorías con confianza.

        Args:
            X: Features (embeddings)

        Returns:
            Lista de (categoria, confianza) para cada sample
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        probas = self.model.predict_proba(X)
        predictions = []

        for proba in probas:
            best_idx = np.argmax(proba)
            best_category = self.classes_[best_idx]
            best_confidence = proba[best_idx]
            predictions.append((best_category, best_confidence))

        return predictions

    def save(self, path: str):
        """
        Guarda el modelo entrenado.

        Args:
            path: Path al archivo .pkl
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(
            {
                "model": self.model,
                "model_type": self.model_type,
                "classes": self.classes_,
                "label_encoder": self.label_encoder,
            },
            path,
        )

        print(f"  ✓ Model saved: {path}")

    @classmethod
    def load(cls, path: str) -> "SupervisedClassifier":
        """
        Carga un modelo guardado.

        Args:
            path: Path al archivo .pkl

        Returns:
            SupervisedClassifier cargado
        """
        data = joblib.load(path)

        classifier = cls(model_type=data["model_type"])
        classifier.model = data["model"]
        classifier.classes_ = data["classes"]
        classifier.label_encoder = data["label_encoder"]
        classifier.is_trained = True

        print(f"  ✓ Model loaded: {path}")
        return classifier

    def get_feature_importance(self, feature_names: Optional[List[str]] = None) -> Optional[np.ndarray]:
        """
        Obtiene importancia de features (si el modelo lo soporta).

        Args:
            feature_names: Nombres de features (opcional)

        Returns:
            Array de importancias o None si no disponible
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        if hasattr(self.model, "feature_importances_"):
            return self.model.feature_importances_
        elif hasattr(self.model, "coef_"):
            # Para logistic regression, usar magnitud de coeficientes
            return np.abs(self.model.coef_).mean(axis=0)
        else:
            return None


if __name__ == "__main__":
    # Test
    print("Testing SupervisedClassifier...")

    # Datos sintéticos
    np.random.seed(42)
    X_train = np.random.randn(1000, 384)  # 1000 samples, 384 features
    y_train = np.random.choice(["economia", "politica", "tecnologia"], size=1000)

    X_test = np.random.randn(200, 384)
    y_test = np.random.choice(["economia", "politica", "tecnologia"], size=200)

    # Test Logistic Regression
    print("\n=== Logistic Regression ===")
    clf_lr = SupervisedClassifier(model_type="logistic_regression")
    train_metrics = clf_lr.train(X_train, y_train, cv_folds=5)
    test_metrics = clf_lr.evaluate(X_test, y_test)

    # Test predictions
    preds = clf_lr.predict(X_test[:5])
    print(f"\nSample predictions: {preds}")

    preds_conf = clf_lr.predict_with_confidence(X_test[:5])
    print(f"With confidence: {preds_conf}")

    # Test save/load
    clf_lr.save("test_model.pkl")
    clf_loaded = SupervisedClassifier.load("test_model.pkl")
    print(f"Loaded model type: {clf_loaded.model_type}")

    # Test XGBoost (if available)
    if HAS_XGBOOST:
        print("\n=== XGBoost ===")
        clf_xgb = SupervisedClassifier(model_type="xgboost")
        train_metrics = clf_xgb.train(X_train, y_train, cv_folds=3)
        test_metrics = clf_xgb.evaluate(X_test, y_test)

    print("\n✓ All tests passed")
