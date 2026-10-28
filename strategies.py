"""
Fighter strategy guides for the fighter pages.

input/fighter_strategies_short.md and input/fighter_strategies.md hold one entry per fighter,
each starting with <!-- id: ... -->. The entries use a small, fixed subset of Markdown
(### headings, paragraphs, - and 1. lists, **bold**, *italic*, `code`, [text](url), bare URLs
and [n] citations), so they're rendered here rather than with a Markdown library.

The v2 guides (research/GUIDES-V2.md) come in three versions, Short, Medium and Card by card, in
input/fighter_guides_{short,medium,cards}.md; until a fighter has one, the older guides stand in.
Card names in a guide are matched against the fighter's deck and shown as hover cards.
"""
import re

from markupsafe import Markup, escape

_ENTRY = re.compile(r"<!-- id: (\S+) -->\n(.*?)(?=\n<!-- id: |\Z)", re.S)
_HEADINGS = {"Not cited": "More to read and watch"}
# Reference [1] of every entry is the deck; on the site it's the deck list further down the page
_DECK_NOTE = "Card text as recorded in `input/heroes.json`."
_PLACEHOLDER = ""  # private-use character, never in the text
# Card titles as printed where the data spells them differently
_TITLE_FIXES = {"Shapershifter": "Shapeshifter"}
_NOT_CARD_NAMES = {"Again"}  # one-word titles that are mostly ordinary words in a guide
_APOSTROPHE = "&#39;"  # how escape() writes ' (guides also use ’)


def load(path):
    """{fighter id: entry text} for one strategy file; {} if it's missing."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return {}
    return {m.group(1): m.group(2).strip() for m in _ENTRY.finditer(text)}


def _clean_title(title):
    """Card title without symbols such as Little Red's basket emoji."""
    title = re.sub(r"[^\w\s'\-\.,!?:\"&’]", "", title).strip()
    return _TITLE_FIXES.get(title, title)


def _card_pop(card, fighter_name):
    """Inner HTML of a card's hover box."""
    facts = [str(escape(card.get("type") or "").capitalize())]
    if card.get("value") is not None:
        facts.append(f"value {card['value']}")
    if card.get("boost") is not None:
        facts.append(f"boost {card['boost']}")
    facts.append(f"×{card.get('copies', 1)}")
    who = card.get("character")
    who = "" if not who or who in ("Any", fighter_name) else f'<span class="card-pop-who">{escape(who)}</span>'
    effect = f'<span class="card-pop-effect">{escape(card["effect"])}</span>' if card.get("effect") else ""
    return (f'<span class="card-pop-title">{escape(_clean_title(card["title"]))}</span>{who}'
            f'<span class="card-pop-facts">{" · ".join(facts)}</span>{effect}')


def card_matcher(deck, fighter_name=""):
    """(compiled regex, {escaped title: popup html}) for linking this deck's card names, or None."""
    pops = {}
    for card in deck or []:
        title = _clean_title(card.get("title", ""))
        if len(title) < 3 or title in _NOT_CARD_NAMES:
            continue
        pops.setdefault(str(escape(title)), _card_pop(card, fighter_name))
    if not pops:
        return None
    # Longest first, so "Feint" never takes the start of a longer title; all-caps titles (Loki's,
    # Pandora's) are written in normal capitals in the guides, so those match in any case
    alts = []
    for title in sorted(pops, key=len, reverse=True):
        body = f"(?:{re.escape(_APOSTROPHE)}|’)".join(re.escape(part) for part in title.split(_APOSTROPHE))
        alts.append(f"(?i:{body})" if title.isupper() else body)
    pattern = re.compile(r"(?<![\w&])(" + "|".join(alts) + r")(?![\w])")
    lookup = {k.lower(): v for k, v in pops.items()}
    return pattern, lookup


def _pop_for(lookup, name):
    return lookup[name.replace("’", _APOSTROPHE).lower()]


def _inline(text, ref_prefix, sup=True, cards=None):
    s = str(escape(text))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    links = []

    def link_html(html):
        links.append(html)
        return f"{_PLACEHOLDER}{len(links) - 1}{_PLACEHOLDER}"

    def link(label, url):
        return link_html(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')

    # Links and card hovers become placeholders first, so the bold/italic/citation rules below
    # can't touch URLs or card text
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: link(m.group(1), m.group(2)), s)
    s = re.sub(r"https?://[^\s<]+?(?=[.,;)]?(?:\s|$))", lambda m: link(m.group(0), m.group(0)), s)
    if cards:
        pattern, lookup = cards
        s = pattern.sub(lambda m: link_html(
            f'<span class="card-ref" tabindex="0">{m.group(1)}'
            f'<span class="card-pop" role="tooltip">{_pop_for(lookup, m.group(1))}</span></span>'), s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    cite = '<sup class="cite"><a href="#{p}-ref-{n}">[{n}]</a></sup>' if sup else '<a href="#{p}-ref-{n}">[{n}]</a>'
    s = re.sub(r"\[(\d+)\]", lambda m: cite.format(p=ref_prefix, n=m.group(1)), s)
    return re.sub(f"{_PLACEHOLDER}(\\d+){_PLACEHOLDER}", lambda m: links[int(m.group(1))], s)


def render(entry, ref_prefix, cards=None):
    """HTML for one entry, without its id line, fighter-name heading and closing separator.

    cards is a card_matcher() result: those card names in the guide text become hover cards.
    """
    out, lst, section = [], None, None

    def close():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None

    for line in entry.splitlines():
        line = line.rstrip()
        if not line or line == "---" or line.startswith(("<!--", "## ")):
            close()
            continue
        if line.startswith("### "):
            close()
            section = line[4:].strip()
            slug = re.sub(r"[^a-z]+", "-", section.lower()).strip("-")
            out.append(f'<h3 class="guide-{slug}">{escape(_HEADINGS.get(section, section))}</h3>')
            continue
        item = re.match(r"(\d+)\. (.*)", line)
        if item and section == "References":
            if lst != "ol":
                close()
                out.append('<ol class="guide-refs">')
                lst = "ol"
            text = item.group(2).replace(_DECK_NOTE, "Card text as in the deck list below.")
            out.append(f'<li id="{ref_prefix}-ref-{item.group(1)}" value="{item.group(1)}">'
                       f'{_inline(text, ref_prefix, sup=False)}</li>')
            continue
        if line.startswith("- "):
            text = line[2:]
            if section == "Not cited":
                if "(read;" in text:
                    continue  # read during the research and judged not useful for this fighter
                text = re.sub(r"\s*\(not yet reviewed\)$", "", text)
            if lst != "ul":
                close()
                out.append("<ul>")
                lst = "ul"
            out.append(f"<li>{_inline(text, ref_prefix, cards=cards)}</li>")
            continue
        close()
        if section == "References":
            continue  # research notes on the deck data, not part of the guide
        out.append(f"<p>{_inline(line, ref_prefix, cards=cards)}</p>")
    close()
    return Markup("\n".join(out))


def load_guides(short_path, medium_path, v2_paths=None, heroes=None, names=None):
    """{fighter id: {"short", "medium", "cards": html or None}}.

    v2_paths maps "short"/"medium"/"cards" to the v2 guide files. Where a fighter has no v2 guide
    yet, the older short guide stands in for Short and the older full guide for Medium. heroes
    ({id: hero data}) and names ({id: fighter name}) give each guide its deck's hover cards.
    """
    old = {"short": load(short_path), "medium": load(medium_path)}
    new = {kind: load(path) for kind, path in (v2_paths or {}).items()}
    heroes, names = heroes or {}, names or {}
    guides = {}
    for fid in set().union(*old.values(), *new.values()):
        cards = card_matcher((heroes.get(fid) or {}).get("deck"), names.get(fid, ""))
        guide = {}
        for kind, prefix in (("short", "s"), ("medium", "m"), ("cards", "c")):
            if fid in new.get(kind, {}):
                guide[kind] = render(new[kind][fid], prefix, cards)
            elif fid in old.get(kind, {}):
                guide[kind] = render(old[kind][fid], prefix)
            else:
                guide[kind] = None
        guides[fid] = guide
    return guides
