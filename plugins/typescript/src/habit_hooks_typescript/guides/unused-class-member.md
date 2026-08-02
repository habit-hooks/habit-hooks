A method or property no code outside the class ever touches — and that the class itself never uses — is dead surface pretending to be part of the design. It inflates the class's apparent responsibilities, invites a reader to reason about a collaboration that doesn't exist, and is the kind of thing a later change "maintains" for no reason.

First rule out a false alarm: a member reached only by reflection, a framework lifecycle hook, or a decorator can be live yet invisible to static analysis — if that's the case, make the use legible rather than deleting a real seam. Otherwise decide which kind of dead it is. If nothing needs it, delete it and anything that existed only to feed it. If it's *meant* to be used but the caller was never wired up, connect it. And if a cluster of unused members shares state and behaviour, that's usually a class trying to split: extract them into their own unit where they become a real, used public surface instead of a private back room.

Done right, every member of the class is reached by something real, so the class's public shape is an honest statement of what it does.

The unused members:

{% for issue in issues -%}
{{ issue.details.file }}:{{ issue.details.line }}  {{ issue.details.name }}
{% endfor %}
