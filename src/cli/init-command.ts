import { Command } from 'commander';
import { runInit } from './init/run.js';
import { makeAutoPrompter, makeInteractivePrompter, type Prompter } from './init/prompts.js';
import { emit } from './emit.js';

interface InitFlags {
  yes?: boolean;
  defaults?: boolean;
  dryRun?: boolean;
}

function pickPrompter(flags: InitFlags): Prompter {
  if (flags.yes === true) return makeAutoPrompter(true);
  if (flags.defaults === true) return makeAutoPrompter(false);
  if (flags.dryRun === true) return makeAutoPrompter(false);
  return makeInteractivePrompter();
}

async function execute(flags: InitFlags): Promise<void> {
  const prompter = pickPrompter(flags);
  try {
    emit(await runInit(process.cwd(), { prompter, dryRun: flags.dryRun === true }));
  } finally {
    prompter.close();
  }
}

export function registerInitCommand(program: Command): void {
  program
    .command('init')
    .description('detect tools, scaffold missing configs, write a slim habit-hooks config')
    .option('--yes', 'accept every prompt (non-interactive)')
    .option('--defaults', 'take the default answer for every prompt (non-interactive)')
    .option('--dry-run', 'show what would be written without writing')
    .action(async (flags: InitFlags) => {
      await execute(flags);
    });
}
