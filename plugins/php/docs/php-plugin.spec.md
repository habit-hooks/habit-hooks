# The php plugin — acceptance

The php plugin runs its sensor through the real `habit-sensors` pipeline. These
cases run the **actual** tool (PHPMD, bundled as a `.phar` next to the sensor)
against a fixture with a known smell and assert the canonical finding comes out,
mapped to the smell keys in [smell-vocabulary.md](smell-vocabulary.md).

`habit-sensors` is the installed CLI; `php` is on the system `PATH`. The sensor
runs `php phpmd.phar` with PHP error reporting silenced (PHP's deprecation
notices would otherwise leak onto the JSON stdout) and normalises PHPMD's
exit-2-on-violations into a clean run.

📄.habit-hooks/config.toml
```toml
plugins = ["php"]
```

## phpmd sensor maps rule names to canonical smells

The `phpmd` sensor runs PHPMD with the `codesize,unusedcode` rulesets and shapes
each violation into one finding per smell, stamping `source: "phpmd:<rule>"` on
each issue. An eleven-parameter function trips `ExcessiveParameterList` →
`too-many-parameters`, and its dead local trips `UnusedLocalVariable` →
`unused-variable`.

📄billing.php
```php
<?php
function charge($a, $b, $c, $d, $e, $f, $g, $h, $i, $j, $k) {
    $unused = 1;
    return $a + $b + $c + $d + $e + $f + $g + $h + $i + $j + $k;
}
```

```bash
habit-sensors --all | jq 'sort_by(.smell)[] | {smell, language, key: (.issues[0].key | sub(".*/"; "")), line: .issues[0].details.line, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "too-many-parameters",
  "language": "php",
  "key": "billing.php",
  "line": 2,
  "source": "phpmd:ExcessiveParameterList"
}
{
  "smell": "unused-variable",
  "language": "php",
  "key": "billing.php",
  "line": 3,
  "source": "phpmd:UnusedLocalVariable"
}
```

## phpmd sensor maps a deeply-branched function to high-complexity

A function with a dozen independent branches exceeds PHPMD's cyclomatic
complexity threshold, tripping `CyclomaticComplexity` → `high-complexity`.
PHPMD's overlapping `NPathComplexity` is intentionally not mapped, so the same
function reports a single smell.

📄report.php
```php
<?php
function classify($n) {
    if ($n == 1) return 1;
    if ($n == 2) return 2;
    if ($n == 3) return 3;
    if ($n == 4) return 4;
    if ($n == 5) return 5;
    if ($n == 6) return 6;
    if ($n == 7) return 7;
    if ($n == 8) return 8;
    if ($n == 9) return 9;
    if ($n == 10) return 10;
    if ($n == 11) return 11;
    return 0;
}
```

```bash
habit-sensors --all | jq '.[] | {smell, language, source: .issues[0].details.source}'
```

🖥️ ✅
```json
{
  "smell": "high-complexity",
  "language": "php",
  "source": "phpmd:CyclomaticComplexity"
}
```

## A crashing phpmd fails the run, never reports clean

PHPMD exits non-zero on a file it cannot parse. The sensor surfaces that as a
failure — a crashed tool is never a clean run. It exits with a code outside the
findings range, so `habit-sensors` raises, names the sensor on stderr, and exits
1 rather than printing an empty (false-clean) result.

📄broken.php
```php
<?php function ( {
```

```bash
habit-sensors --all
```

🖥️ ❌ 1
```json
[]
```

🚨
```text
habit-sensors: sensor 'phpmd' failed: ${python} ${dir}/phpmd_sensor.py ${files}
```
