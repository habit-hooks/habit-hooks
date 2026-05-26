import readline from 'node:readline';

export interface PromptOptions {
  defaultYes: boolean;
}

export interface Prompter {
  ask(question: string, opts: PromptOptions): Promise<boolean>;
  close(): void;
}

function suffix(defaultYes: boolean): string {
  return defaultYes ? '[Y/n]' : '[y/N]';
}

function interpret(answer: string, defaultYes: boolean): boolean {
  const trimmed = answer.trim().toLowerCase();
  if (trimmed.length === 0) return defaultYes;
  return trimmed === 'y' || trimmed === 'yes';
}

function askVia(rl: readline.Interface, question: string, opts: PromptOptions): Promise<boolean> {
  return new Promise((resolve) => {
    rl.question(`${question} ${suffix(opts.defaultYes)} `, (answer) => {
      resolve(interpret(answer, opts.defaultYes));
    });
  });
}

export function makeInteractivePrompter(): Prompter {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return {
    ask: (q, opts) => askVia(rl, q, opts),
    close: () => rl.close(),
  };
}

export function makeAutoPrompter(defaultYesForAll: boolean): Prompter {
  return {
    ask(_question, opts) {
      return Promise.resolve(defaultYesForAll ? true : opts.defaultYes);
    },
    close() {},
  };
}
