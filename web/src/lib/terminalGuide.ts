export const TERMINAL_WELCOME = [
  'B-Tree Database REPL',
  'Type commands at the db > prompt and press Enter.',
  'A quick reference will appear once Pyodide is ready (or type .help anytime).',
]

export const TERMINAL_QUICK_REFERENCE = [
  '',
  'Pyodide ready — quick reference:',
  '─────────────────────────────────',
  '  insert <id> <username> <email>   Add a row (id is the B-Tree key)',
  '  select                           Print all rows in key order',
  '',
  '  .btree                           Print tree + refresh visualizer',
  '  .constants                       Show page layout constants',
  '  .help                            Show this guide again',
  '  .exit                            Close the database',
  '',
  'Tips:',
  '  • Click a node in the visualizer to inspect its memory map',
  '  • Each leaf page holds up to 3 keys — more inserts cause splits',
  '  • Use Import / Export .db in the header to save your work',
  '',
  'Try:  insert 1 alice alice@example.com',
]
