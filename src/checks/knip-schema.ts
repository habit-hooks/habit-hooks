export interface KnipLocation {
  name: string;
  line?: number;
  col?: number;
}

export type KnipMemberMap = Record<string, KnipLocation[]>;

export interface KnipIssue {
  file: string;
  files?: KnipLocation[];
  dependencies?: KnipLocation[];
  devDependencies?: KnipLocation[];
  optionalPeerDependencies?: KnipLocation[];
  unlisted?: KnipLocation[];
  binaries?: KnipLocation[];
  unresolved?: KnipLocation[];
  exports?: KnipLocation[];
  nsExports?: KnipLocation[];
  types?: KnipLocation[];
  nsTypes?: KnipLocation[];
  duplicates?: KnipLocation[][];
  enumMembers?: KnipMemberMap;
  classMembers?: KnipMemberMap;
  namespaceMembers?: KnipMemberMap;
  catalog?: KnipLocation[];
}

export interface KnipReport {
  files?: string[];
  issues?: KnipIssue[];
}

export const LOCATION_KEYS: (keyof KnipIssue)[] = [
  'files',
  'dependencies',
  'devDependencies',
  'optionalPeerDependencies',
  'unlisted',
  'binaries',
  'unresolved',
  'exports',
  'nsExports',
  'types',
  'nsTypes',
  'catalog',
];

export const MEMBER_KEYS: (keyof KnipIssue)[] = ['enumMembers', 'classMembers', 'namespaceMembers'];

export const CODE_KEYS: string[] = ['exports', 'nsExports', 'types', 'nsTypes', ...(MEMBER_KEYS as string[])];

const STRUCTURAL_KEYS = new Set<string>(['file']);
const SPECIAL_KEYS = new Set<string>(['duplicates']);

export const KNOWN_KEYS = new Set<string>([
  ...STRUCTURAL_KEYS,
  ...SPECIAL_KEYS,
  ...(LOCATION_KEYS as string[]),
  ...(MEMBER_KEYS as string[]),
]);
