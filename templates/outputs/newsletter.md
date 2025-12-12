# {{ newsletter_name }}

{% if newsletter_description %}
> {{ newsletter_description }}
{% endif %}

**Fecha:** {{ date }}
**Generado:** {{ generated_at }}
**Artículos totales:** {{ total_articles }} ({{ articles_with_content }} con contenido completo)

---

{{ content }}

---

## 📋 Fuentes de este newsletter
{% set global_counter = namespace(value=0) %}
{% for category, articles_in_cat in articles|groupby('category') %}
### {{ category|default('sin categoria')|title }}

{% for article in articles_in_cat %}
{% set global_counter.value = global_counter.value + 1 %}
{{ global_counter.value }}. [{{ article.title }}]({{ article.url }}){% if article.has_full_content %} ✓{% endif %}

{% endfor %}
{% endfor %}

---

*Newsletter generado automáticamente por Newsletter Utils Pipeline*
