{% for v in issues -%}
{{ v.details.file }}:{{ v.details.line }} {{ v.details.message }}
{% endfor %}
Resolve or remove these markers before merging.
