import { runTool } from '../wrap/shell.js';
import { isSpawnFailure } from '../wrap/notices.js';
import type { GuideAction } from '../mapper/mapper.js';

// Running a `command` fix: the script receives the smell's whole bag as JSON on
// stdin and runs once. A spawn/timeout failure is a blocking config error (it
// always blocks); a clean non-zero exit blocks only an `enforced` smell; exit 0
// means handled and never blocks. The script's output is shown to the agent.
export interface CommandRun {
  output: string;
  blocks: boolean;
}

function combinedOutput(stdout: string, stderr: string): string {
  return [stdout, stderr]
    .map((stream) => stream.trimEnd())
    .filter((stream) => stream.length > 0)
    .join('\n');
}

export async function runFixCommand(action: GuideAction, scriptPath: string, cwd: string): Promise<CommandRun> {
  const result = await runTool({ bin: scriptPath, args: [], cwd, stdin: JSON.stringify(action.issues) });
  if (isSpawnFailure(result)) {
    const detail = result.warnings.length > 0 ? result.warnings.join('; ') : 'spawn failure';
    return { output: `❌ fix command for ${action.smell} could not run: ${detail}`, blocks: true };
  }
  return {
    output: combinedOutput(result.stdout, result.stderr),
    blocks: result.exitCode !== 0 && action.severity === 'enforced',
  };
}
