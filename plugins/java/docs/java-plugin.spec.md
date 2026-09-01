# The java plugin — acceptance

The java plugin runs its sensor through the real `habit-sensors` pipeline. These
cases run the **actual** tool (PMD, from the system `PATH`) against a fixture
with a known smell and assert the canonical finding comes out, mapped to the
smell keys in [smell-vocabulary.md](smell-vocabulary.md).

`habit-sensors` is the installed CLI; `pmd` is on the system `PATH`. The sensor
runs `pmd check --format json`, normalises PMD's exit-4-on-violations into a
clean run, and reaches for a ruleset the project wrote only after checking the
conventional Java locations, then falls back to the bundled `pmd-ruleset.xml`
when the project has none (PMD itself never discovers one).

📄.habit-hooks/config.toml
```toml
plugins = ["java"]
```

## pmd sensor maps rule names to canonical smells

The `pmd` sensor runs PMD with the bundled fallback ruleset and shapes each
violation into one finding per smell, stamping `source: "pmd:<rule>"` on each
issue. A five-parameter constructor trips `ExcessiveParameterList` →
`too-many-parameters`, an unused import trips `UnnecessaryImport` →
`unused-import`, and a dead local trips `UnusedLocalVariable` →
`unused-variable`.

📄Billing.java
```java
import java.io.File;
import java.io.IOException;
class Billing {
    double charge(double a, double b, double c, double d, double e) {
        int dead = 1;
        return a + b + c + d + e;
    }
}
```

```bash
habit-sensors --all | jq 'sort_by(.smell)[] | {smell, language, key: (.issues[0].key | sub(".*/"; "")), line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "too-many-parameters",
  "language": "java",
  "key": "Billing.java",
  "line": 4,
  "source": "pmd:ExcessiveParameterList"
}
{
  "smell": "unused-import",
  "language": "java",
  "key": "Billing.java",
  "line": 1,
  "source": "pmd:UnnecessaryImport"
}
{
  "smell": "unused-variable",
  "language": "java",
  "key": "Billing.java",
  "line": 5,
  "source": "pmd:UnusedLocalVariable"
}
```

## pmd sensor reports the third nested if from the bundled ruleset

With no PMD ruleset in the project, the plugin's bundled fallback explicitly
sets `AvoidDeeplyNestedIfStmts` to report depth 3. The finding points at the
third `if` and translates the PMD rule to the shared `deep-nesting` smell.

📄Nested.java
```java
class Nested {
    boolean accepts(int value) {
        if (value > 0) {
            if (value < 10) {
                if (value != 5) {
                    return true;
                }
            }
        }
        return false;
    }
}
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: (.issues[0].key | sub(".*/"; "")), line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "deep-nesting",
  "language": "java",
  "key": "Nested.java",
  "line": 5,
  "source": "pmd:AvoidDeeplyNestedIfStmts"
}
```

## two nested ifs remain below the bundled threshold

The third nested `if` is the first one PMD reports at `problemDepth=3`, so an
otherwise equivalent two-level chain remains clean.

📄Nested.java
```java
class Nested {
    boolean accepts(int value) {
        if (value > 0) {
            if (value < 10) {
                return true;
            }
        }
        return false;
    }
}
```

```bash
habit-sensors --all | jq '[.[].smell]'
```

🖥️ ✅
```json
[]
```

## pmd sensor maps a deeply-branched method to high-complexity

A method whose conditions are littered with `||` exceeds PMD's cyclomatic
complexity threshold, tripping `CyclomaticComplexity` → `high-complexity` — while
staying short enough on NCSS that the method is not also flagged oversized.

📄Report.java
```java
class Report {
    int classify(int n) {
        if (n == 1 || n == 2 || n == 3 || n == 4 || n == 5) return 1;
        if (n == 6 || n == 7 || n == 8 || n == 9 || n == 10) return 2;
        if (n == 11 || n == 12 || n == 13 || n == 14 || n == 15) return 3;
        if (n == 16 || n == 17 || n == 18) return 4;
        return 0;
    }
}
```

```bash
habit-sensors --all | jq '.[] | {smell, language, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "high-complexity",
  "language": "java",
  "source": "pmd:CyclomaticComplexity"
}
```

## A project's own ruleset wins over the bundled one

PMD never discovers a project ruleset, so the sensor reaches for one only where
the Java ecosystem conventionally keeps it. A `src/main/resources/pmd/ruleset.xml`
that lowers the parameter threshold is in force for the run — the bundled
fallback is only the answer to "this project has none". The source also has
three nested `if`s, but this project ruleset omits `AvoidDeeplyNestedIfStmts`,
so only the rule the project selected produces a finding.

📄src/main/resources/pmd/ruleset.xml
```xml
<?xml version="1.0"?>
<ruleset name="custom" xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">
 <description>two parameters is already too many</description>
 <rule ref="category/java/design.xml/ExcessiveParameterList">
  <properties><property name="minimum" value="2"/></properties>
 </rule>
</ruleset>
```

📄Project.java
```java
class Project {
    void save(String a, String b) {
        if (a != null) {
            if (b != null) {
                if (!a.equals(b)) {
                    System.out.println(a);
                }
            }
        }
    }
}
```

```bash
habit-sensors --all | jq '.[] | {smell, language, key: (.issues[0].key | sub(".*/"; ""))}'
```

🖥️ ✅
```json
{
  "smell": "too-many-parameters",
  "language": "java",
  "key": "Project.java"
}
```

## a project ruleset can enable deep nesting at its own threshold

A project can opt into the same PMD rule with a different `problemDepth`. Its
ruleset still replaces the bundled fallback as a whole; the sensor translates
the enabled rule normally.

📄pmd/ruleset.xml
```xml
<?xml version="1.0"?>
<ruleset name="custom" xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">
 <description>report the second nested if</description>
 <rule ref="category/java/design.xml/AvoidDeeplyNestedIfStmts">
  <properties><property name="problemDepth" value="2"/></properties>
 </rule>
</ruleset>
```

📄Nested.java
```java
class Nested {
    boolean accepts(int value) {
        if (value > 0) {
            if (value < 10) {
                return true;
            }
        }
        return false;
    }
}
```

```bash
habit-sensors --all | jq '.[] | {smell, language, line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "deep-nesting",
  "language": "java",
  "line": 4,
  "source": "pmd:AvoidDeeplyNestedIfStmts"
}
```

## `[sensors.pmd] args` reaches PMD directly

`args` is spliced into the sensor's command as `${args} -- ${files}`, so a real
PMD flag — not just a ruleset — passes straight through to `pmd check`.
`ExcessiveParameterList` reports at priority 3 and `UnnecessaryImport` at
priority 4, so `--minimum-priority 3` keeps the parameter-list violation and
drops the import one: proof the flag reached PMD's own filtering rather than
becoming a bogus file argument the sensor could not find.

📄.habit-hooks/config.toml
```toml
plugins = ["java"]

[sensors.pmd]
args = ["--minimum-priority", "3"]
```

📄Billing.java
```java
import java.io.File;
class Billing {
    double charge(double a, double b, double c, double d, double e) {
        return a + b + c + d + e;
    }
}
```

```bash
habit-sensors --all | jq '.[] | {smell, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "too-many-parameters",
  "source": "pmd:ExcessiveParameterList"
}
```

## A crashing pmd fails the run, never reports clean

PMD exits non-zero on a file it cannot parse. The sensor surfaces that as a
failure — a crashed tool is never a clean run. It exits with a code outside the
findings range, so `habit-sensors` raises, names the sensor on stderr, and exits
1 rather than printing an empty (false-clean) result. The failed run carries only
the reserved `incomplete-run` marker on stdout
([habit-sensors.spec.md](../../../docs/habit-sensors.spec.md)).

The notice carries PMD's own diagnosis after that first line.

📄broken.java
```java
class Broken {
    void oops( {
}
```

```bash
habit-sensors --all | jq -c '[.[].smell]'
```

🖥️ ❌ 1
```json
["incomplete-run"]
```

```bash
habit-sensors --all 2>&1 >/dev/null | sed -n 1p
```

🖥️ ❌ 1
```text
habit-sensors: sensor 'pmd' failed: '${python}' '${dir}/pmd_sensor.py' '${detector:pmd}' '${args}' -- '${files}'
```
