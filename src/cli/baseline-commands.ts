import { Command } from 'commander';
import {
  baselineForget,
  baselineGenerate,
  baselinePrune,
  baselineSnooze,
  baselineStatus,
  type CommandResult,
} from '../baseline/commands.js';
import { emit } from './emit.js';

async function runAction(action: () => Promise<CommandResult> | CommandResult): Promise<void> {
  try {
    emit(await action());
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`habit-hooks: ${message}\n`);
    process.exitCode = 2;
  }
}

function attachGenerate(baseline: Command): void {
  baseline
    .command('generate')
    .description('record currently-violating files as snoozed')
    .action(async () => {
      await runAction(() => baselineGenerate(process.cwd()));
    });
}

function attachStatus(baseline: Command): void {
  baseline
    .command('status')
    .description('list snoozed files and their freshness')
    .action(async () => {
      await runAction(() => baselineStatus(process.cwd()));
    });
}

function attachSnooze(baseline: Command): void {
  baseline
    .command('snooze <files...>')
    .description('snooze the given tracked files')
    .action(async (files: string[]) => {
      await runAction(() => baselineSnooze(process.cwd(), files));
    });
}

function attachForget(baseline: Command): void {
  baseline
    .command('forget <files...>')
    .description('remove baseline entries for the given files')
    .action(async (files: string[]) => {
      await runAction(() => baselineForget(process.cwd(), files));
    });
}

function attachPrune(baseline: Command): void {
  baseline
    .command('prune')
    .description('remove stale entries (missing files or resolved violations)')
    .action(async () => {
      await runAction(() => baselinePrune(process.cwd()));
    });
}

export function registerBaselineCommands(program: Command): void {
  const baseline = program.command('baseline').description('manage the snooze baseline');
  attachGenerate(baseline);
  attachStatus(baseline);
  attachSnooze(baseline);
  attachForget(baseline);
  attachPrune(baseline);
}
