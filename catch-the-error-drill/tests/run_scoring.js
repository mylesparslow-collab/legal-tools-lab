// Test bridge: reads {"calls": [{"fn": name, "args": [...]}]} on stdin, prints the results as JSON.
'use strict';
const path = require('path');
const S = require(path.join(__dirname, '..', 'app', 'scoring.js'));
let input = '';
process.stdin.on('data', (c) => { input += c; });
process.stdin.on('end', () => {
  const calls = JSON.parse(input).calls;
  process.stdout.write(JSON.stringify(calls.map((c) => {
    if (c.fn === 'const') { return S[c.args[0]]; }
    return S[c.fn].apply(null, c.args);
  })));
});
