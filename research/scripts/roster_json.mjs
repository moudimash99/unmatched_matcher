import { writeFileSync } from 'node:fs';
const r = (await import(process.argv[2])).default.roster;
writeFileSync(process.argv[3], JSON.stringify(r.map(f => ({ id: f.id, name: f.name, set: f.set[0] }))));
