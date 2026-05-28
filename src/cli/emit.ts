interface CommandOutput {
  stdout: string;
  stderr: string;
  exitCode: number;
}

export function emit(result: CommandOutput): void {
  if (result.stdout.length > 0) process.stdout.write(result.stdout);
  if (result.stderr.length > 0) process.stderr.write(result.stderr);
  process.exitCode = result.exitCode;
}
