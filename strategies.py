"""
Fighter strategy guides for the fighter pages.

input/fighter_strategies_short.md and input/fighter_strategies.md hold one entry per fighter,
each starting with <!-- id: ... -->. The entries use a small, fixed subset of Markdown
(### headings, paragraphs, - and 1. lists, **bold**, *italic*, `code`, [text](url), bare URLs
and [n] citations), so they're rendered here rather than with a Markdown library.
"""
import re

from markupsafe import Markup, escape

_ENTRY = re.compile(r"<!-- id: (\S+) -->\n(.*?)(?=\n<!-- id: |\Z)", re.S)
_HEADINGS = {"Not cited": "More to read and watch"}
# Reference [1] of every entry is the deck; on the site it's the deck list further down the page
_DECK_NOTE = "Card text as recorded in `input/heroes.json`."
_PLACEHOLDER = ""  # private-use character, never in the text


def load(path):
    """{fighter id: entry text} for one strategy file; {} if it's missing."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return {}
    return {m.group(1): m.group(2).strip() for m in _ENTRY.finditer(text)}


def _inline(text, ref_prefix, sup=True):
    s = str(escape(text))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    links = []

    def link(label, url):
        links.append(f'<a href="{url}" target="_blank" rel="noopener">{label}</a>')
        return f"{_PLACEHOLDER}{len(links) - 1}{_PLACEHOLDER}"

    # Links become placeholders first, so the bold/italic/citation rules below can't touch URLs
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: link(m.group(1), m.group(2)), s)
    s = re.sub(r"https?://[^\s<]+?(?=[.,;)]?(?:\s|$))", lambda m: link(m.group(0), m.group(0)), s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    cite = '<sup class="cite"><a href="#{p}-ref-{n}">[{n}]</a></sup>' if sup else '<a href="#{p}-ref-{n}">[{n}]</a>'
    s = re.sub(r"\[(\d+)\]", lambda m: cite.format(p=ref_prefix, n=m.group(1)), s)
    return re.sub(f"{_PLACEHOLDER}(\\d+){_PLACEHOLDER}", lambda m: links[int(m.group(1))], s)


def render(entry, ref_prefix):
    """HTML for one entry, without its id line, fighter-name heading and closing separator."""
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
            out.append(f"<li>{_inline(text, ref_prefix)}</li>")
            continue
        close()
        out.append(f"<p>{_inline(line, ref_prefix)}</p>")
    close()
    return Markup("\n".join(out))


def load_guides(short_path, medium_path):
    """{fighter id: {"short": html, "full": html}}; either is None when its file has no entry."""
    short, medium = load(short_path), load(medium_path)
    return {
        fid: {
            "short": render(short[fid], "s") if fid in short else None,
            "full": render(medium[fid], "f") if fid in medium else None,
        }
        for fid in short.keys() | medium.keys()
    }
