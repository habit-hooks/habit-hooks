import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';

export interface ShellResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  warnings: string[];
}

interface RunToolOptions {
  bin: string;
  args: string[];
  cwd: string;
  timeoutMs?: number;
}

interface StreamBuffers {
  stdout: Buffer[];
  stderr: Buffer[];
}

interface Settler {
  resolve: (_result: ShellResult) => void;
  done: { value: boolean };
  clearTimer: () => void;
}

const DEFAULT_TIMEOUT_MS = 5 * 60 * 1000;

function emptyFailure(warning: string): ShellResult {
  return { stdout: '', stderr: '', exitCode: -1, warnings: [warning] };
}

function collectStreams(child: ChildProcessWithoutNullStreams): StreamBuffers {
  const buffers: StreamBuffers = { stdout: [], stderr: [] };
  child.stdout.on('data', (chunk: Buffer) => buffers.stdout.push(chunk));
  child.stderr.on('data', (chunk: Buffer) => buffers.stderr.push(chunk));
  return buffers;
}

function settleOnce(settler: Settler, result: ShellResult): void {
  if (settler.done.value) return;
  settler.done.value = true;
  settler.clearTimer();
  settler.resolve(result);
}

interface CloseInfo {
  buffers: StreamBuffers;
  bin: string;
  code: number | null;
  signal: NodeJS.Signals | null;
}

function closeResult(info: CloseInfo): ShellResult {
  if (info.signal !== null) return emptyFailure(`${info.bin} terminated by signal ${info.signal}`);
  const stdout = Buffer.concat(info.buffers.stdout).toString('utf8');
  const stderr = Buffer.concat(info.buffers.stderr).toString('utf8');
  return { stdout, stderr, exitCode: info.code ?? -1, warnings: [] };
}

function startKillTimer(child: ChildProcessWithoutNullStreams, onTimeout: () => void, timeoutMs: number): NodeJS.Timeout {
  return setTimeout(() => {
    child.kill('SIGKILL');
    onTimeout();
  }, timeoutMs);
}

export function runTool(opts: RunToolOptions): Promise<ShellResult> {
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  return new Promise((resolve) => {
    const child = spawn(opts.bin, opts.args, { cwd: opts.cwd });
    const buffers = collectStreams(child);
    const done = { value: false };
    const timer = startKillTimer(child, () => settleOnce(settler, emptyFailure(`${opts.bin} timed out after ${timeoutMs}ms`)), timeoutMs);
    const settler: Settler = { resolve, done, clearTimer: () => clearTimeout(timer) };
    child.on('error', (e) => settleOnce(settler, emptyFailure(`${opts.bin} failed to spawn: ${e.message}`)));
    child.on('close', (code, signal) => settleOnce(settler, closeResult({ buffers, bin: opts.bin, code, signal })));
  });
}
