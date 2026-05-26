import { readFileSync } from 'node:fs';
import { existsSync } from 'node:fs';

export const exists = (p: string): boolean => existsSync(p);
export const read = (p: string): string => readFileSync(p, 'utf8');
