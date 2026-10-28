You are writing the **Short** version of a strategy guide for the Unmatched fighter **{name}** (site id `{id}`). Write it to `research/private/guides/{id}.short.md`. Do not edit any other file.

Your only material is the fighter's approved **Medium** guide, `research/private/guides/{id}.medium.md` (and its evidence file, `{id}.medium.evidence.md`, if you need to check a claim). The Short version condenses it: **every claim must already be in the Medium guide, with the same sources.** Don't add anything.

## Rules

- Never name another Unmatched fighter; the Medium guide already describes opponents by type, keep that.
- Card names in full, exactly as in the Medium guide (the site turns them into hover cards).
- Every claim carries a numbered citation [n] pointing to this entry's own References list, numbered in order of first use. Copy the reference lines word for word from the Medium guide, renumbered. Put a space before each citation and write several as `[1][3]`.
- Plain, direct, second person. No filler.
- Only these Markdown features: `###` headings, flat `- ` lists, `1. ` lists under References, `**bold**`, [n] citations.

## Format: about 150 words before References

```
<!-- id: {id} -->
## {name}

**In short:** one sentence.

### How they win
- **Win condition name:** when to choose it, and the card or two that make it work. (One bullet per win condition in the Medium guide, at most 3.)

### How they lose
- **Threat:** the answer, with a card. (2 bullets)

### References
1. …

---
```

Print the word count when done.
