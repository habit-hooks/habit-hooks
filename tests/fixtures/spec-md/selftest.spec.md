# spec-md self-test

This fixture is deterministic and uses only shell built-ins so the framework
can be exercised without the mapper CLI. It is never run by the data provider
because `tests/fixtures/**` is excluded from the spec glob.

### echo prints a single line

```bash
echo hello
```

```text
hello
```

**Expected outcome:** Success

### a failing command reports its exit code

```bash
bash -c 'exit 3'
```

**Expected outcome:** Fails with 3

### ellipsis matches a trailing run of lines

```bash
printf 'a\nb\nc\n'
```

```text
a
...
```

**Expected outcome:** Success

### multiple units run in order

```bash
printf 'first\nsecond\n'
```

```text
first
...
second
```

```bash
echo done
```

```text
done
```

**Expected outcome:** Success
