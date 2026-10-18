import { readFileSync, writeFileSync } from 'node:fs';
const [dataPath, uploadPath, outPath] = process.argv.slice(2);
const roster = (await import(dataPath)).default.roster;
// Gridbeast links from the user's own list
const grid = {};
for (const m of readFileSync(uploadPath, 'utf8').matchAll(/\|\s*([^|]*?)\s*\|\s*(https:\/\/gridbeast\.gg\/unmatched-[^\s|]+)/g)) grid[m[1]] = m[2];
const alias = { 'InGen':'Robert Muldoon', 'William Shakespeare':'Shakespeare', 'Little Red Riding Hood':'Little Red Riding Hood',
  'Rosie The Riveter':'Rosie the Riveter', 'Geralt of Rivia':'Geralt' };
const strip = s => (s||'').replace(/<br\s*\/?>/gi,' ').replace(/<[^>]+>/g,'').replace(/\s+/g,' ').trim();
const q = s => `"${String(s ?? '').replace(/"/g,'""')}"`;
const cols = ['id','fighter','set','ability_text','roster_summary','how_it_wins','how_it_loses','strong_against','weak_against','gridbeast_guide','video_guides','deck_page'];
const rows = [cols.join(',')];
let gb = 0;
for (const f of roster) {
  const name = f.name === 'InGen' ? 'Robert Muldoon (InGen)' : f.name;
  const g = grid[alias[f.name] ?? f.name] ?? grid[f.name] ?? '';
  if (g) gb++;
  rows.push([f.id, name, f.set[0], strip(f.ability), strip(f.desc), '', '', '', '', g,
    (f.guides||[]).map(x=>`${x.name}: ${x.url}`).join(' ; '), f.deck].map(q).join(','));
}
writeFileSync(outPath, rows.join('\n') + '\n');
console.log('rows', roster.length, 'with gridbeast', gb);
console.log('no gridbeast:', roster.filter(f=>!(grid[alias[f.name] ?? f.name] ?? grid[f.name])).map(f=>f.name).join(', '));
