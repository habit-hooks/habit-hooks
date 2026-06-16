#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { Command, CommanderError, Option } from 'commander';
import { runWithAutoPrune } from './baseline/auto-prune.js';
import { registerBaselineCommands } from './cli/baseline-commands.js';
import { registerInitCommand } from './cli/init-command.js';
import type { ScopeFlags } from './git/resolve-scope.js';

const here = dirname(fileURLToPath(import.meta.url));
const packageJsonPath = join(here, '..', 'package.json');
const pkg = JSON.parse(readFileSync(packageJsonPath, 'utf8')) as { version: string };

interface CliOptions {
  version?: boolean;
  config?: string;
  last?: string;
  branch?: string | true;
  since?: string;
  all?: boolean;
}

function reportError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`habit-hooks: ${message}\n`);
  process.exitCode = 2;
}

function parseLast(value: string): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1 || String(parsed) !== value) {
    throw new Error(`--last must be a positive integer, got '${value}'`);
  }
  return parsed;
}

function toScopeFlags(opts: CliOptions): ScopeFlags {
  const flags: ScopeFlags = {};
  if (opts.all === true) flags.all = true;
  if (opts.last !== undefined) flags.last = parseLast(opts.last);
  if (opts.since !== undefined) flags.since = opts.since;
  if (opts.branch !== undefined) flags.branch = opts.branch === true ? '' : opts.branch;
  return flags;
}

async function executeRun(opts: CliOptions): Promise<void> {
  const configPath = opts.config !== undefined ? resolve(process.cwd(), opts.config) : undefined;
  const scopeFlags = toScopeFlags(opts);
  const result = await runWithAutoPrune(process.cwd(), { configPath, scopeFlags });
  process.stdout.write(result.stdout);
  for (const line of result.stderr) process.stderr.write(`${line}\n`);
  process.exitCode = result.exitCode;
}

async function runWithOptions(opts: CliOptions): Promise<void> {
  if (opts.version === true) {
    process.stdout.write(`habit-hooks v${pkg.version}\n`);
    return;
  }
  try {
    await executeRun(opts);
  } catch (error) {
    reportError(error);
  }
}

const program = new Command();

program
  .name('habit-hooks')
  .exitOverride()
  .option('--version', 'print version')
  .option('--config <path>', 'path to a habit-hooks config file')
  .addOption(
    new Option('--last <n>', 'check files changed in the last N commits').conflicts([
      'branch',
      'since',
      'all',
    ]),
  )
  .addOption(
    new Option('--branch [name]', 'check files changed vs branch (default: scope.branchBase)').conflicts(
      ['last', 'since', 'all'],
    ),
  )
  .addOption(
    new Option('--since <hash>', 'check files changed since the given commit').conflicts([
      'last',
      'branch',
      'all',
    ]),
  )
  .addOption(
    new Option('--all', 'force checking all files (ignore scope config)').conflicts([
      'last',
      'branch',
      'since',
    ]),
  )
  .action(async () => {
    await runWithOptions(program.opts<CliOptions>());
  });

registerBaselineCommands(program);
registerInitCommand(program);

function handleCommanderError(error: CommanderError): void {
  if (error.code === 'commander.helpDisplayed' || error.code === 'commander.help') {
    return;
  }
  process.exitCode = 2;
}

try {
  await program.parseAsync(process.argv);
} catch (error) {
  if (error instanceof CommanderError) {
    handleCommanderError(error);
  } else {
    reportError(error);
  }
}
