import { Command } from 'commander';
import { runInit } from './init/run.js';
import { makeAutoPrompter, makeInteractivePrompter, type Prompter } from './init/prompts.js';
import { emit } from './emit.js';

interface InitFlags {
  yes?: boolean;
  defaults?: boolean;
}

function pickPrompter(flags: InitFlags): Prompter {
  if (flags.yes === true) return makeAutoPrompter(true);
  if (flags.defaults === true) return makeAutoPrompter(false);
  return makeInteractivePrompter();
}

async function execute(flags: InitFlags): Promise<void> {
  const prompter = pickPrompter(flags);
  try {
    emit(await runInit(process.cwd(), { prompter }));
  } finally {
    prompter.close();
  }
}

export function registerInitCommand(program: Command): void {
  program
    .command('init')
    .description('scaffold habit-hooks config, baseline, and optional integrations')
    .option('--yes', 'accept every prompt (non-interactive)')
    .option('--defaults', 'take the default answer for every prompt (non-interactive)')
    .action(async (flags: InitFlags) => {
      await execute(flags);
    });
}
