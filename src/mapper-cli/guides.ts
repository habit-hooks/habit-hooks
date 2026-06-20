import { loadTsModule } from '../config/jiti-loader.js';
import type { Guides } from './run.js';

function installPromptGlobal(): void {
  (globalThis as Record<string, unknown>).prompt = (text: string): string => text;
}

function asGuides(module: unknown): Guides {
  if (typeof module !== 'object' || module === null) {
    throw new Error('guides module must export a default object of smell -> function');
  }
  return module as Guides;
}

export async function loadGuides(absolutePath: string): Promise<Guides> {
  installPromptGlobal();
  return asGuides(await loadTsModule(absolutePath));
}
