const r = (await import(process.argv[2])).default.roster;
const seen = new Map();
for (const f of r) { const [n,u] = f.set; if (!seen.has(n)) seen.set(n,u); }
for (const [n,u] of seen) console.log(`| ${n} | [BoardGameGeek](${u}) |`);
