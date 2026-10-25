const r = (await import(process.argv[2])).default.roster;
const setName = {
  'Battle of Legends, Volume One':'Battle of Legends 1','Bruce Lee':'Bruce Lee (2020 box)',
  'Jurassic Park - Ingen vs. Raptors':'Jurassic Park: InGen vs. Raptors','Buffy the Vampire Slayer':'Buffy',
  'Little Red Riding Hood vs. Beowulf':'Little Red vs. Beowulf','Unmatched: Battle of Legends, Volume Two':'Battle of Legends 2',
  'Redemption Row':'Marvel: Redemption Row',"Hell's Kitchen":"Marvel: Hell's Kitchen",'Jurassic Park - Sattler vs. T-Rex':'Jurassic Park: Sattler vs. T. Rex',
  'Teen Spirit':'Marvel: Teen Spirit','For King and Country':'Marvel: For King and Country','Brains and Brawn':'Marvel: Brains and Brawn',
  'Unmatched Adventures: Tales to Amaze':'Tales to Amaze','Steel and Silver':'The Witcher: Steel & Silver','Realms Fall':'The Witcher: Realms Fall',
  'Battle of Legends, Volume Three':'Battle of Legends 3','Lee vs Ali':'Bruce Lee vs. Ali',
  'Unmatched Adventures: Teenage Mutant Ninja Turtles':'TMNT Adventures','Unmatched Adventures: Teenage Mutant Ninja Turtles - Shredder and Krang':'TMNT: Shredder vs. Krang',
  'Unmatched: Stars and Stripes':'Stars and Stripes'};
const nameFix = { 'InGen':'Robert Muldoon (InGen)' };
let last = null;
console.log('| Set | Fighter | Video strategy guides | Deck list / hero page |');
console.log('|---|---|---|---|');
for (const f of r) {
  const s = setName[f.set[0]] ?? f.set[0];
  const g = (f.guides||[]).map(x=>`[${x.name}](${x.url})`).join(' · ') || 'none listed yet';
  const deckLabel = f.deck.includes('the-unmatched.club') ? 'Unmatched Club' : 'UMDB';
  console.log(`| ${s===last?'':s} | ${nameFix[f.name]??f.name} | ${g} | [${deckLabel}](${f.deck}) |`);
  last = s;
}
