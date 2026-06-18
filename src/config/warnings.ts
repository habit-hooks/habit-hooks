import { RULES_DEPRECATION, SENSORS_FALLBACK_DEPRECATION, UNKNOWN_LANGUAGE_NO_FILES } from './load.js';
import { defaultSensorIds } from '../sensors/registry.js';
import type { HabitHooksConfig } from './schema.js';

// The preset fallback warns only when it would actually supply sensors — an
// unknown language has an empty preset, so warning there would mislead.
export function collectConfigWarnings(config: HabitHooksConfig, language: string): string[] {
  const warnings: string[] = [];
  if (config.rules !== undefined) warnings.push(RULES_DEPRECATION);
  if (config.sensors === undefined && defaultSensorIds(language).length > 0) warnings.push(SENSORS_FALLBACK_DEPRECATION);
  if (defaultSensorIds(language).length === 0 && config.files === undefined) warnings.push(UNKNOWN_LANGUAGE_NO_FILES);
  return warnings;
}
