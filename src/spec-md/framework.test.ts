import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseSpec } from '../../tests/helpers/spec-md/parser.js';
import { checkUnit, matchesExpected, normalize, runUnit } from '../../tests/helpers/spec-md/runner.js';

const TWO_EXAMPLES = `# title

prose that never runs

### First example

\`\`\`bash
echo one
\`\`\`

\`\`\`text
one
\`\`\`

**Expected outcome:** Success

\`\`\`bash
false
\`\`\`

**Expected outcome:** Fails with 1

### Second example

\`\`\`bash
echo two
\`\`\`

## A level-2 heading closes the example

\`\`\`bash
echo orphaned
\`\`\`
`;

const PROSE_ONLY = `### Just prose

No bash block here.

### Has a command

\`\`\`bash
echo hi
\`\`\`
`;

describe('parseSpec', () => {
  it('parses two examples with titles, commands, stdout and exit codes', () => {
    const examples = parseSpec(TWO_EXAMPLES);
    expect(examples.map((e) => e.title)).toEqual(['First example', 'Second example']);
    const first = examples[0];
    expect(first.units).toHaveLength(2);
    expect(first.units[0]).toEqual({ command: 'echo one', expectedStdout: 'one', expectedExit: 0 });
    expect(first.units[1]).toEqual({ command: 'false', expectedStdout: null, expectedExit: 1 });
  });

  it('defaults exit to 0 and stdout to null when absent', () => {
    const second = parseSpec(TWO_EXAMPLES)[1];
    expect(second.units).toEqual([{ command: 'echo two', expectedStdout: null, expectedExit: 0 }]);
  });

  it('treats a level-2 heading as the end of an example', () => {
    const commands = parseSpec(TWO_EXAMPLES)
      .flatMap((e) => e.units)
      .map((u) => u.command);
    expect(commands).not.toContain('echo orphaned');
  });

  it('yields empty units for a prose-only example', () => {
    const examples = parseSpec(PROSE_ONLY);
    expect(examples[0]).toEqual({ title: 'Just prose', units: [] });
    expect(examples[1].units).toHaveLength(1);
  });

  it('reads Fails with 0 as exit 0', () => {
    const spec = '### Zero\n\n```bash\ntrue\n```\n\n**Expected outcome:** Fails with 0\n';
    expect(parseSpec(spec)[0].units[0].expectedExit).toBe(0);
  });

  it('joins a multi-line bash block with newlines', () => {
    const spec = '### Multi\n\n```bash\ncd somewhere\necho here\n```\n';
    expect(parseSpec(spec)[0].units[0].command).toBe('cd somewhere\necho here');
  });

  it('does not treat a heading line inside a fenced block as an example boundary', () => {
    const spec = '### Heading inside text\n\n```bash\necho hi\n```\n\n```text\n## Not a heading\nmore\n```\n\n**Expected outcome:** Success\n';
    const example = parseSpec(spec)[0];
    expect(example.units).toHaveLength(1);
    expect(example.units[0].expectedStdout).toBe('## Not a heading\nmore');
  });
});

describe('normalize', () => {
  it('strips ANSI escape sequences', () => {
    expect(normalize('[31mred[0m')).toBe('red');
  });

  it('strips trailing whitespace and trailing blank lines', () => {
    expect(normalize('a   \nb\t\n\n\n')).toBe('a\nb');
  });
});

describe('matchesExpected', () => {
  it('matches identical text', () => {
    expect(matchesExpected('a\nb', 'a\nb')).toBe(true);
  });

  it('lone ellipsis matches zero lines', () => {
    expect(matchesExpected('...', '')).toBe(true);
  });

  it('lone ellipsis matches many lines', () => {
    expect(matchesExpected('...', 'a\nb\nc')).toBe(true);
  });

  it('trailing ellipsis allows extra lines after a literal prefix', () => {
    expect(matchesExpected('a\n...', 'a\nb\nc')).toBe(true);
  });

  it('leading ellipsis allows lines before a literal suffix', () => {
    expect(matchesExpected('...\nc', 'a\nb\nc')).toBe(true);
  });

  it('interior ellipsis allows a gap between two literal blocks', () => {
    expect(matchesExpected('a\n...\nd', 'a\nb\nc\nd')).toBe(true);
  });

  it('returns false on a genuine mismatch', () => {
    expect(matchesExpected('a\nb', 'a\nx')).toBe(false);
  });

  it('requires the final literal block to end flush without a trailing ellipsis', () => {
    expect(matchesExpected('a', 'a\nb')).toBe(false);
  });
});

describe('runUnit', () => {
  it('runs a successful command', async () => {
    const result = await runUnit({ command: 'echo hello', expectedStdout: null, expectedExit: 0 }, { cwd: process.cwd() });
    expect(result).toEqual({ stdout: 'hello\n', exitCode: 0 });
  });

  it('reports a non-zero exit code', async () => {
    const result = await runUnit({ command: "bash -c 'exit 3'", expectedStdout: null, expectedExit: 3 }, { cwd: process.cwd() });
    expect(result.exitCode).toBe(3);
  });
});

describe('end-to-end on the selftest fixture', () => {
  it('parses and runs every unit successfully', async () => {
    const markdown = readFileSync('tests/fixtures/spec-md/selftest.spec.md', 'utf8');
    const examples = parseSpec(markdown);
    expect(examples.length).toBeGreaterThan(0);
    for (const example of examples) {
      for (const unit of example.units) {
        const result = await runUnit(unit, { cwd: process.cwd() });
        const check = checkUnit(unit, result);
        expect(check.ok, check.ok ? '' : check.message).toBe(true);
      }
    }
  });
});
