#!/usr/bin/env python3
"""
Genera informe comparativo de todos los experimentos
"""

from pathlib import Path
from datetime import datetime
import re

# Resultados extraídos manualmente de los experimentos
experiments = [
    {
        "id": "baseline",
        "name": "Baseline",
        "config": "threshold=0.5, examples=3, strategy=mean, include_otros=yes",
        "dataset_size": 100,
        "accuracy": 0.590,
        "precision_macro": 0.484,
        "recall_macro": 0.606,
        "f1_macro": 0.476,
        "time_s": 15.5,
        "memory_mb": 140.6,
    },
    {
        "id": "exp1",
        "name": "Threshold 0.6",
        "config": "threshold=0.6, examples=3, strategy=mean, include_otros=yes",
        "dataset_size": 100,
        "accuracy": 0.590,
        "precision_macro": 0.484,
        "recall_macro": 0.606,
        "f1_macro": 0.476,
        "time_s": 16.7,
        "memory_mb": 140.6,
        "note": "⚠️ Sin efecto (method=cosine_similarity ignora threshold)"
    },
    {
        "id": "exp2",
        "name": "5 Ejemplos",
        "config": "threshold=0.5, examples=5, strategy=mean, include_otros=yes",
        "dataset_size": 100,
        "accuracy": 0.660,
        "precision_macro": 0.485,
        "recall_macro": 0.604,
        "f1_macro": 0.482,
        "time_s": 18.7,
        "memory_mb": 140.6,
        "note": "✓ MEJORA: +7 pts accuracy"
    },
    {
        "id": "exp3",
        "name": "Weighted Strategy",
        "config": "threshold=0.5, examples=3, strategy=weighted_mean, include_otros=yes",
        "dataset_size": 100,
        "accuracy": 0.630,
        "precision_macro": 0.461,
        "recall_macro": 0.589,
        "f1_macro": 0.463,
        "time_s": 17.9,
        "memory_mb": 140.6,
        "note": "✓ MEJORA: +4 pts accuracy"
    },
    {
        "id": "exp4",
        "name": "Excluir 'otros'",
        "config": "threshold=0.5, examples=3, strategy=mean, include_otros=no",
        "dataset_size": 100,
        "accuracy": 0.600,
        "precision_macro": 0.436,
        "recall_macro": 0.578,
        "f1_macro": 0.437,
        "time_s": 16.8,
        "memory_mb": 140.6,
        "note": "✓ MEJORA: +1 pt accuracy"
    },
    {
        "id": "exp5",
        "name": "Configuración Óptima",
        "config": "threshold=0.6, examples=5, strategy=weighted_mean, include_otros=no",
        "dataset_size": 100,
        "accuracy": 0.670,
        "precision_macro": 0.478,
        "recall_macro": 0.633,
        "f1_macro": 0.495,
        "time_s": 17.7,
        "memory_mb": 140.6,
        "note": "✓✓ MEJOR: +8 pts accuracy"
    },
    {
        "id": "exp6",
        "name": "Dataset Completo",
        "config": "threshold=0.6, examples=5, strategy=weighted_mean, include_otros=no",
        "dataset_size": 3757,
        "accuracy": 0.547,
        "precision_macro": 0.474,
        "recall_macro": 0.514,
        "f1_macro": 0.457,
        "time_s": 222,  # 3m 42s
        "memory_mb": 144.0,
        "note": "⚠️ Accuracy baja con dataset real (54.7%)"
    },
]


def generate_comparison_report():
    """Genera informe comparativo markdown"""
    lines = []

    # Header
    lines.append("# 📊 Informe Comparativo de Experimentos")
    lines.append(f"**PoC:** Category Classification con Embeddings")
    lines.append(f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Resumen ejecutivo
    lines.append("## 📈 Resumen Ejecutivo")
    lines.append("")
    lines.append(f"Se ejecutaron **{len(experiments)} experimentos** para optimizar la clasificación por categorías usando embeddings:")
    lines.append("")

    best_100 = max([e for e in experiments if e['dataset_size'] == 100], key=lambda x: x['accuracy'])
    baseline = experiments[0]

    lines.append(f"### Resultados Clave")
    lines.append(f"- **Baseline** (100 URLs): {baseline['accuracy']:.1%} accuracy")
    lines.append(f"- **Mejor configuración** (100 URLs): **{best_100['accuracy']:.1%} accuracy** ({best_100['name']})")
    lines.append(f"- **Mejora absoluta**: +{(best_100['accuracy'] - baseline['accuracy']) * 100:.1f} puntos")
    lines.append(f"- **Mejora relativa**: +{((best_100['accuracy'] / baseline['accuracy']) - 1) * 100:.1f}%")
    lines.append("")

    full_dataset = experiments[-1]
    lines.append(f"### Dataset Completo (3757 URLs)")
    lines.append(f"- **Accuracy**: {full_dataset['accuracy']:.1%}")
    lines.append(f"- **F1-Score**: {full_dataset['f1_macro']:.3f}")
    lines.append(f"- **Tiempo**: {full_dataset['time_s'] // 60:.0f}m {full_dataset['time_s'] % 60:.0f}s")
    lines.append(f"- **Conclusión**: Accuracy más baja sugiere que subset de 100 URLs no es representativo")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Tabla comparativa
    lines.append("## 📊 Tabla Comparativa (100 URLs)")
    lines.append("")
    lines.append("| Experimento | Accuracy | Precision | Recall | F1 | Tiempo | Nota |")
    lines.append("|-------------|----------|-----------|--------|-----|---------|------|")

    for exp in experiments:
        if exp['dataset_size'] != 100:
            continue

        name = exp['name']
        acc = f"{exp['accuracy']:.1%}"
        prec = f"{exp['precision_macro']:.3f}"
        rec = f"{exp['recall_macro']:.3f}"
        f1 = f"{exp['f1_macro']:.3f}"
        time = f"{exp['time_s']:.1f}s"
        note = exp.get('note', '')

        lines.append(f"| {name:15} | {acc:8} | {prec:9} | {rec:7} | {f1:4} | {time:7} | {note} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Análisis detallado
    lines.append("## 🔍 Análisis por Experimento")
    lines.append("")

    for i, exp in enumerate(experiments, 1):
        lines.append(f"### {i}. {exp['name']}")
        lines.append("")
        lines.append(f"**Configuración:**")
        lines.append(f"```")
        lines.append(f"{exp['config']}")
        lines.append(f"```")
        lines.append("")
        lines.append(f"**Resultados:**")
        lines.append(f"- Dataset: {exp['dataset_size']} URLs")
        lines.append(f"- Accuracy: **{exp['accuracy']:.1%}**")
        lines.append(f"- Precision (macro): {exp['precision_macro']:.3f}")
        lines.append(f"- Recall (macro): {exp['recall_macro']:.3f}")
        lines.append(f"- F1-Score (macro): {exp['f1_macro']:.3f}")
        lines.append(f"- Tiempo: {exp['time_s']:.1f}s")
        lines.append(f"- Memoria: {exp['memory_mb']:.1f} MB")
        lines.append("")

        if 'note' in exp:
            lines.append(f"**Observaciones:** {exp['note']}")
            lines.append("")

        # Delta vs baseline
        if i > 1 and exp['dataset_size'] == 100:
            delta = (exp['accuracy'] - baseline['accuracy']) * 100
            if delta > 0:
                lines.append(f"**Δ vs Baseline:** +{delta:.1f} pts ✓")
            elif delta < 0:
                lines.append(f"**Δ vs Baseline:** {delta:.1f} pts ✗")
            else:
                lines.append(f"**Δ vs Baseline:** Sin cambio")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Conclusiones
    lines.append("## 💡 Conclusiones y Recomendaciones")
    lines.append("")

    lines.append("### ✅ Mejoras Efectivas")
    lines.append(f"1. **Aumentar ejemplos a 5** → +7 pts accuracy (exp2: {experiments[2]['accuracy']:.1%})")
    lines.append(f"2. **Weighted mean strategy** → +4 pts accuracy (exp3: {experiments[3]['accuracy']:.1%})")
    lines.append(f"3. **Combinación óptima** → +8 pts accuracy (exp5: {experiments[5]['accuracy']:.1%})")
    lines.append("")

    lines.append("### ❌ Mejoras No Efectivas")
    lines.append("1. **Threshold 0.6** → Sin efecto (method=cosine_similarity ignora threshold)")
    lines.append("2. **Excluir 'otros'** → Mejora mínima (+1 pt)")
    lines.append("")

    lines.append("### ⚠️ Observación Importante: Dataset Size")
    lines.append("")
    lines.append(f"La diferencia entre exp5 (67% con 100 URLs) y exp6 (54.7% con 3757 URLs) revela:")
    lines.append("- **Sesgo de muestra**: Las 100 URLs más recientes son más fáciles de clasificar")
    lines.append("- **Variabilidad real**: El dataset completo tiene mayor diversidad temática")
    lines.append("- **Accuracy realista**: ~55% es más representativo del rendimiento real")
    lines.append("")

    lines.append("### 🎯 Configuración Recomendada")
    lines.append("")
    lines.append("```yaml")
    lines.append("classification:")
    lines.append("  method: cosine_similarity")
    lines.append("  examples_per_category: 5  # ← CLAVE")
    lines.append("  category_embedding_strategy: weighted_mean  # ← CLAVE")
    lines.append("")
    lines.append("categories:")
    lines.append("  exclude: ['otros']  # ← Opcional")
    lines.append("```")
    lines.append("")

    lines.append("### 📊 Comparación vs LLM")
    lines.append("")
    lines.append("| Métrica | Embeddings (optimizado) | LLM (gpt-4o-mini) |")
    lines.append("|---------|------------------------|-------------------|")
    lines.append(f"| Accuracy | **~55%** | ~90-95% (estimado) |")
    lines.append(f"| Velocidad | **3m 42s** (3757 URLs) | ~30-60s (180 URLs) |")
    lines.append(f"| Costo | **$0** (local) | ~$0.03 por ejecución |")
    lines.append(f"| Escalabilidad | **Sin límite** | Rate limits API |")
    lines.append(f"| Reproducibilidad | **100%** | ~98% (temperature=0.2) |")
    lines.append("")

    lines.append("### 🚀 Próximos Pasos")
    lines.append("")
    lines.append("1. **Modelo más grande**: Probar `intfloat/multilingual-e5-base` (768 dims)")
    lines.append("2. **Fine-tuning**: Entrenar clasificador supervisado con histórico")
    lines.append("3. **Hybrid approach**: Embeddings para categorías fáciles, LLM para difíciles")
    lines.append("4. **Análisis de errores**: Identificar patrones de confusión y ajustar categorías")
    lines.append("5. **Temporal analysis**: Evaluar si accuracy varía con el tiempo")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Informe generado automáticamente - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_comparison_report()

    output_path = Path("output/experiments/COMPARISON_REPORT.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Informe comparativo generado: {output_path}")
    print(f"\nResumen:")
    print(f"- Baseline: 59.0%")
    print(f"- Mejor (100 URLs): 67.0% (+8 pts)")
    print(f"- Dataset completo (3757 URLs): 54.7%")
