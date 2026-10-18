const r = (await import(process.argv[2])).default.roster;
const seen = new Map();
for (const f of r) { const [n,u] = f.set||[]; if (!seen.has(n)) seen.set(n, [u, []]); seen.get(n)[1].push(f.name); }
for (const [n,[u,fs]] of seen) console.log(`${n}\t${u}\t${fs.join(', ')}`);
