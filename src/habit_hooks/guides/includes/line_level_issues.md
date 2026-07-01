{% for issue in issues -%}
{{ issue.details.file }}:{{ issue.details.line }}{% if issue.details.content %}  {{ issue.details.content }}{% endif %}
{% endfor -%}
