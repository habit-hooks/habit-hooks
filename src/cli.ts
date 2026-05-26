#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { Command } from 'commander';

const here = dirname(fileURLToPath(import.meta.url));
const packageJsonPath = join(here, '..', 'package.json');
const pkg = JSON.parse(readFileSync(packageJsonPath, 'utf8')) as { version: string };

const program = new Command();

program
  .name('habit-hooks')
  .option('--version', 'print version')
  .action(() => {
    process.stdout.write(`habit-hooks v${pkg.version}\n`);
  });

program.parse(process.argv);
