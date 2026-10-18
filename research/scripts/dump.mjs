const mod = await import(process.argv[2]);
const r = mod.default.roster;
for (const f of r) {
  const g = (f.guides||[]).map(x=>`${x.name}: ${x.url}`).join(' | ');
  console.log(`${f.id}\t${f.name}\t${(f.set||[])[0]}\t${f.deck||''}\t${g||'-'}`);
}
console.error('count', r.length);
