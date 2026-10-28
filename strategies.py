"""
Fighter strategy guides for the fighter pages.

input/fighter_strategies_short.md and input/fighter_strategies.md hold one entry per fighter,
each starting with <!-- id: ... -->. The entries use a small, fixed subset of Markdown
(### headings, paragraphs, - and 1. lists, **bold**, *italic*, `code`, [text](url), bare URLs
and [n] citations), so they're rendered here rather than with a Markdown library.

The v2 guides (research/GUIDES-V2.md) come in three versions, Short, Medium and Card by card, in
input/fighter_guides_{short,medium,cards}.md; until a fighter has one, the older guides stand in.
Card names in a guide are matched against the fighter's deck and shown as hover cards, with the
card's picture where input/card_images.json has one.
"""
import re

from markupsafe import Markup, escape

_ENTRY = re.compile(r"<!-- id: (\S+) -->\n(.*?)(?=\n<!-- id: |\Z)", re.S)
_HEADINGS = {"Not cited": "More to read and watch"}
# Reference [1] of every entry is the deck; on the site it's the deck list further down the page
_DECK_NOTE = "Card text as recorded in `input/heroes.json`."
_PLACEHOLDER = ""  # private-use character, never in the text
# Card titles as printed where the data spells them differently
_TITLE_FIXES = {"Shapershifter": "Shapeshifter",
                "Eat, sleep, and breath ninjutsu": "Eat, Sleep, and Breathe Ninjutsu"}
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


def _card_pop(card, fighter_name, image=None):
    """Inner HTML of a card's hover box: the card's picture, or its text when there's no picture."""
    if image:
        alt = f"{_clean_title(card['title'])}: {card.get('effect') or ''}".rstrip(": ")
        return (f'<img class="card-pop-img" src="{escape(image)}" alt="{escape(alt)}" loading="lazy" '
                f'width="250" height="349">')
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


def _term_pop(term, info, note):
    extra = f'<span class="card-pop-effect">{escape(info["text"])}</span>' if info.get("text") else ""
    return (f'<span class="card-pop-title">{escape(info.get("symbol", ""))} {escape(term.capitalize())}</span>{extra}'
            f'<span class="card-pop-effect">{escape(note)}</span>')


def card_matcher(deck, fighter_name="", images=None, terms=None):
    """(compiled regex, {name: (kind, popup html)}, {title: picture url}) for linking card names, or None.

    images maps card titles as in heroes.json to their pictures (input/card_images.json); terms
    ({note, terms: {word: {symbol, text}}}, input/guide_terms.json) are the fighter's own words, such
    as Little Red's basket symbols, explained the same way and matched in any case.
    """
    pops, thumbs = {}, {}
    for card in deck or []:
        title = _clean_title(card.get("title", ""))
        if len(title) < 3 or title in _NOT_CARD_NAMES:
            continue
        image = (images or {}).get(card.get("title"))
        pops.setdefault(str(escape(title)), ("card", _card_pop(card, fighter_name, image)))
        if image:
            thumbs.setdefault(_key(title), image)
    for term, info in (terms or {}).get("terms", {}).items():
        pops.setdefault(str(escape(term)), ("term", _term_pop(term, info, terms.get("note", ""))))
    if not pops:
        return None
    # Longest first, so "Feint" never takes the start of a longer title; all-caps titles (Loki's,
    # Pandora's) are written in normal capitals in the guides, so those match in any case
    alts = []
    for title in sorted(pops, key=len, reverse=True):
        body = f"(?:{re.escape(_APOSTROPHE)}|’)".join(re.escape(part) for part in title.split(_APOSTROPHE))
        alts.append(f"(?i:{body})" if title.isupper() or pops[title][0] == "term" else body)
    pattern = re.compile(r"(?<![\w&])(" + "|".join(alts) + r")(?![\w])")
    lookup = {k.lower(): v for k, v in pops.items()}
    return pattern, lookup, thumbs


def _key(title):
    """A card title for looking it up, whatever its apostrophes and capitals."""
    return title.replace("’", "'").lower()


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
        pattern, lookup, _ = cards
        def ref(m):
            kind, pop = _pop_for(lookup, m.group(1))
            cls = "card-ref" if kind == "card" else "card-ref term-ref"
            return link_html(f'<span class="{cls}" tabindex="0">{m.group(1)}'
                             f'<span class="card-pop" role="tooltip">{pop}</span></span>')
        s = pattern.sub(ref, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    cite = '<sup class="cite"><a href="#{p}-ref-{n}">[{n}]</a></sup>' if sup else '<a href="#{p}-ref-{n}">[{n}]</a>'
    s = re.sub(r"\[(\d+)\]", lambda m: cite.format(p=ref_prefix, n=m.group(1)), s)
    return re.sub(f"{_PLACEHOLDER}(\\d+){_PLACEHOLDER}", lambda m: links[int(m.group(1))], s)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _card_names(text, cards):
    """The card titles a bold line names ("A and B" names two), or None if it isn't only cards."""
    if not cards:
        return None
    names = [n.strip() for n in re.split(r" and |, ", text)]
    if all(cards[0].fullmatch(str(escape(n))) and _pop_for(cards[1], str(escape(n)))[0] == "card" for n in names):
        return names
    return None


def render(entry, ref_prefix, cards=None):
    """HTML for one entry, without its id line, fighter-name heading and closing separator.

    cards is a card_matcher() result: those card names in the guide text become hover cards. A bold
    line on its own starts a box: a way to win, or in the Card by card guide a card, with its picture
    and a jump link above the cards. "- **Label:** text" items show the label on its own line, and
    the sources fold away under the guide.
    """
    out, lst, section = [], None, None
    box = sources = False
    jumps, jump_at = [], None
    thumbs = cards[2] if cards else {}

    def close():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None

    def close_box():
        nonlocal box
        close()
        if box:
            out.append("</div>")
            box = False

    for line in entry.splitlines():
        line = line.rstrip()
        if not line or line == "---" or line.startswith(("<!--", "## ")):
            close()
            continue
        if line.startswith("### "):
            close_box()
            section = line[4:].strip()
            if section in ("References", "Not cited") and not sources:
                out.append('<details class="guide-sources"><summary>Sources</summary>')
                sources = True
            out.append(f'<h3 class="guide-{_slug(section)}">{escape(_HEADINGS.get(section, section))}</h3>')
            if section.startswith("Cards"):
                jump_at = len(out)
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
                out.append("<ul>" if sources else '<ul class="guide-list">')
                lst = "ul"
            label = None if sources else re.match(r"\*\*([^*]+?):?\*\*\s*(.*)", text)
            if label:
                choose = " guide-choose" if label.group(1).lower().startswith("choose this when") else ""
                body = _inline(label.group(2), ref_prefix, cards=cards)
                body = body.replace("<strong>Answer:</strong>", '<span class="guide-answer">Answer</span>')
                out.append(f'<li class="guide-item{choose}"><span class="guide-label">'
                           f'{_inline(label.group(1), ref_prefix, cards=cards)}</span> {body}</li>')
            else:
                out.append(f"<li>{_inline(text, ref_prefix, cards=cards)}</li>")
            continue
        close()
        if section == "References":
            continue  # research notes on the deck data, not part of the guide
        heading = None if sources else re.fullmatch(r"\*\*([^*]+)\*\*", line)
        if heading:
            close_box()
            title = heading.group(1)
            names = _card_names(title, cards)
            if names:
                anchor = f"{ref_prefix}-card-{_slug(title)}"
                jumps.append(f'<a href="#{anchor}">{escape(title)}</a>')
                pics = "".join(f'<img class="guide-thumb" src="{escape(thumbs[_key(n)])}" alt="" loading="lazy" '
                               f'width="48" height="67">' for n in names if _key(n) in thumbs)
                out.append(f'<div class="guide-box guide-card" id="{anchor}">{pics}'
                           f'<h4>{_inline(title, ref_prefix, cards=cards)}</h4>')
            else:
                out.append(f'<div class="guide-box"><h4>{_inline(title, ref_prefix, cards=cards)}</h4>')
            box = True
            continue
        if line.startswith("**In short:**"):
            close_box()
            out.append(f'<p class="guide-lede">{_inline(line, ref_prefix, cards=cards)}</p>')
            continue
        out.append(f"<p>{_inline(line, ref_prefix, cards=cards)}</p>")
    close_box()
    if sources:
        out.append("</details>")
    if jumps and jump_at is not None:
        out.insert(jump_at, '<nav class="guide-jump" aria-label="Cards">' + "".join(jumps) + "</nav>")
    return Markup("\n".join(out))


def load_guides(short_path, medium_path, v2_paths=None, heroes=None, names=None, images=None, terms=None):
    """{fighter id: {"short", "medium", "cards": html or None}}.

    v2_paths maps "short"/"medium"/"cards" to the v2 guide files. Where a fighter has no v2 guide
    yet, the older short guide stands in for Short and the older full guide for Medium. heroes
    ({id: hero data}), names ({id: fighter name}) and images ({id: {card title: picture url}}) give
    each guide its deck's hover cards; terms ({id: {note, terms}}) its explained words.
    """
    old = {"short": load(short_path), "medium": load(medium_path)}
    new = {kind: load(path) for kind, path in (v2_paths or {}).items()}
    heroes, names, images, terms = heroes or {}, names or {}, images or {}, terms or {}
    guides = {}
    for fid in set().union(*old.values(), *new.values()):
        cards = card_matcher((heroes.get(fid) or {}).get("deck"), names.get(fid, ""), images.get(fid),
                             terms.get(fid))
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
