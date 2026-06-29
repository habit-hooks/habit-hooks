const { spawnSync } = require("node:child_process");

const SMELL_BY_KEY = {
  files: "unused-file",
  exports: "unused-export",
  dependencies: "unused-dependency",
  devDependencies: "unused-dependency",
  classMembers: "unused-class-member",
};

function runKnip() {
  return spawnSync("knip", ["--reporter", "json"], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
}

function knipCrashed(result) {
  return result.error != null || result.status === null || result.status > 1;
}

function issuesFor(entry, key) {
  return (entry[key] || []).map((occurrence) => ({
    key: occurrence.name,
    details: {
      name: occurrence.name,
      file: entry.file,
      source: `knip:${key}`,
    },
  }));
}

function findings(report) {
  const grouped = new Map();
  for (const entry of report.issues || []) {
    for (const key of Object.keys(SMELL_BY_KEY)) {
      const smell = SMELL_BY_KEY[key];
      const issues = issuesFor(entry, key);
      if (issues.length === 0) continue;
      const existing = grouped.get(smell) || { smell, details: {}, issues: [] };
      existing.issues.push(...issues);
      grouped.set(smell, existing);
    }
  }
  return [...grouped.values()];
}

function main() {
  const result = runKnip();
  if (knipCrashed(result)) {
    process.stderr.write(result.stderr || String(result.error));
    return 2;
  }
  process.stdout.write(JSON.stringify(findings(JSON.parse(result.stdout))));
  return 0;
}

process.exit(main());
