An unused field, method, or property is dead surface that makes a type appear to
have responsibilities and collaborations it does not exercise. It asks readers
to understand and maintain behavior that may not exist.

Investigate every occurrence before changing it. Static analysis may not see
reflection, annotations or decorators, serialization, framework lifecycle
hooks, dependency injection, generated callers, or other dynamic uses. When one
of those mechanisms owns the call, preserve the member and make that use legible
to the detector or future readers.

Once those hidden uses are ruled out, choose the design that makes the type
honest: connect an intended caller, extract a cohesive group of members into a
real unit, or remove a member confirmed to be dead together with code that
exists only to support it. Do not remove a member automatically from this
report alone.

The unused members:

{% for issue in issues -%}
{{ issue.details.file }}:{{ issue.details.line }}  {% if issue.details.name is defined %}{{ issue.details.name }}{% else %}{{ issue.details.message }}{% endif %}
{% endfor %}
