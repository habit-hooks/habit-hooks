const files = process.argv.slice(2);

const issues = files.map((file) => ({
  smell: 'custom-go-smell',
  details: { file, line: 1, message: 'custom Go sensor flagged this file' },
}));

process.stdout.write(JSON.stringify({ issues }));
