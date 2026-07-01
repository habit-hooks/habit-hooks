{% for issue in issues -%}
{{ issue.details.file }}{% if issue.details.content %}  {{ issue.details.content }}{% endif %}
{% endfor -%}
