#!/usr/bin/env node
import { resolve } from 'node:path';
import { Command, CommanderError } from 'commander';
import { loadGuides } from './mapper-cli/guides.js';
import { readStdin } from './mapper-cli/stdin.js';
import { runMapper } from './mapper-cli/run.js';

interface MapperOptions {
  guides: string;
}

function reportError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`mapper: ${message}\n`);
  process.exitCode = 2;
}

async function execute(opts: MapperOptions): Promise<void> {
  const guides = await loadGuides(resolve(process.cwd(), opts.guides));
  const result = runMapper(await readStdin(), guides);
  process.stdout.write(result.stdout);
  process.exitCode = result.exitCode;
}

const program = new Command();
program
  .name('mapper')
  .description('route sensor issues through a guides module (reads issues JSON on stdin)')
  .requiredOption('--guides <path>', 'path to a guides module (.ts/.js)')
  .exitOverride()
  .action(async () => {
    try {
      await execute(program.opts<MapperOptions>());
    } catch (error) {
      reportError(error);
    }
  });

try {
  await program.parseAsync(process.argv);
} catch (error) {
  if (error instanceof CommanderError) {
    if (error.code !== 'commander.helpDisplayed' && error.code !== 'commander.help') {
      process.exitCode = error.exitCode === 0 ? 0 : 2;
    }
  } else {
    reportError(error);
  }
}
