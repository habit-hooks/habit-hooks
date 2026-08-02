A dependency declared in the manifest but imported nowhere is a standing liability: it enlarges the install, widens the supply-chain surface every audit has to clear, and lies to the next reader about what this project actually relies on. "Harmless and unused" is exactly the profile of the package a compromised release rides in on.

Remove it from the manifest. Before you do, confirm the tool is right that nothing uses it — a dependency reached only through a plugin system, a config string, or a build step can be real yet invisible to static analysis. If that is the case the fix is to make the use legible (declare the plugin, reference it where the tool can see it), not to leave a dependency that looks unused. If it truly is dead weight, drop it and reinstall so the lockfile forgets it too.

Done right, every entry in the manifest earns its place by being imported, and the dependency list is an honest account of the project's real surface.

These dependencies are declared but unused:

{% for issue in issues -%}
{{ issue.key }}
{% endfor %}
