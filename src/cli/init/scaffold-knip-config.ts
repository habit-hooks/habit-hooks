import { TOOL_CONFIG_FILENAMES } from '../../detect/tool.js';
import { KNIP_CONFIG_FILENAME, KNIP_CONFIG_TEMPLATE } from './templates/knip-config.js';
import { scaffoldFile, type ScaffoldResult } from './scaffold-config.js';

export function scaffoldKnipConfig(cwd: string): ScaffoldResult {
  return scaffoldFile(cwd, TOOL_CONFIG_FILENAMES.knip, KNIP_CONFIG_FILENAME, KNIP_CONFIG_TEMPLATE);
}
