# habit-hooks init

`habit-hooks init` sets a project up. It detects the languages the project is
written in, writes `.habit-hooks/config.toml` enabling a plugin for each, and
reports whatever still stands between the project and a first run — the plugins
nobody has, and the tools those plugins reach for — beside the command that
installs each one. At a terminal it then offers to run those commands; inside a
git hook or a CI job, where nobody is there to answer, it prints them and stops.
It exits 0 either way: `init` configures and reports, and it did both.

Nothing is scanned here. `init` reports on the run this project *would* get; the
run itself is [habit-hooks.spec.md](habit-hooks.spec.md).

Every case below keeps its plugins in the project, under `.habit-hooks/<name>/`
— the vendoring route a project uses when its install cannot add extras. It is
also what makes these cases answer from the files they write rather than from
whatever happens to be installed on the machine running them. Each config here
is cut down to the one key `init` reads, the tools that plugin needs installed;
a project vendoring a plugin for real copies the whole directory, because these
files **replace** the installed plugin's rather than adding to them.

`init` asks git which files the project keeps, so `GIT_CEILING_DIRECTORIES` stops
that question walking up out of the case directory and being answered about the
repository these specs run inside. A real project needs no such thing.

✏️GIT_CEILING_DIRECTORIES
```text
$PWD/..
```

📄.habit-hooks/generic/config.toml
```toml
detectors = []
```

📄.habit-hooks/python/config.toml
```toml
detectors = []
```

📄pyproject.toml
```toml
[project]
name = "acme"
```

## A project with no config gets one naming the plugins it needs

`pyproject.toml` says this project is Python, so `init` plans the `python`
plugin and the languageless `generic` one — `generic` last, because `plugins`
order is the priority the mapper reads. Both are on hand and neither needs a
tool, so nothing stands in the way and the report says where to go next.

```bash
habit-hooks init
```

🖥️ ✅
```text
Detected: python.
Wrote .habit-hooks/config.toml, enabling python, generic.

Nothing missing — run `habit-hooks` to see what it finds.
```

The config it wrote is the smallest one that runs — the plugins, and nothing
else assumed on the project's behalf:

```bash
cat .habit-hooks/config.toml
```

🖥️ ✅
```text
plugins = ["python", "generic"]
```

## A tool the plugins need and this machine has not got

A plugin declares the tools its sensors reach for, and `init` looks for each one
where a run would spawn it. What is missing is named beside the command that
installs it, in the order the plugins declared them, so the list can be worked
through from the top. The run still exits 0: `init` configured this project and
reported on it, which is its whole job — the tool is missing either way.

`< /dev/null` is a run with nobody at the keyboard, which is what `init` gets
inside a git hook or a CI job: it prints the commands and stops. At a terminal
it offers to run them for you.

📄.habit-hooks/generic/config.toml
```toml
detectors = [{ name = "wobble", kind = "command", install = "brew install wobble" }]
```

```bash
habit-hooks init < /dev/null
```

🖥️ ✅
```text
Detected: python.
Wrote .habit-hooks/config.toml, enabling python, generic.

Tools this machine has not got:
  wobble   brew install wobble

Install these, then run `habit-hooks`.
```

## A re-run reports on the project and changes nothing

Running `init` again is how someone asks why a run is reporting nothing, so it
must never be the thing that changed the answer: the config is left exactly as
it was, comments and all, and the report is about the run this project really
gets. The language it detected is still named even where the config covers
something else — here `python` is detected and only `generic` is enabled, which
is the commonest reason a Python project's run finds nothing.

📄.habit-hooks/config.toml
```toml
# mine, and not to be rewritten
plugins = ["generic"]
```

```bash
habit-hooks init
```

🖥️ ✅
```text
Detected: python.
Already configured: .habit-hooks/config.toml enables generic. Left as it is.

Nothing missing — run `habit-hooks` to see what it finds.
```

```bash
cat .habit-hooks/config.toml
```

🖥️ ✅
```text
# mine, and not to be rewritten
plugins = ["generic"]
```
