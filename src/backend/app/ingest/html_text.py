"""HTML (raw or entity-escaped, as Greenhouse sends it) -> plain text or markdown."""
import html
import re

from bs4 import BeautifulSoup, Comment, NavigableString

BLOCK = {"p", "div", "section", "article", "header", "footer", "blockquote", "table", "tr",
         "h1", "h2", "h3", "h4", "h5", "h6"}
SKIP = {"script", "style", "noscript", "head", "meta", "iframe", "svg", "form", "button"}
MD = {"strong": "**", "b": "**", "em": "*", "i": "*"}


def unescape_html(raw: str) -> str:
    """Greenhouse 'content' is entity-escaped (&lt;div&gt;...). Decode until it's real HTML."""
    raw = raw or ""
    while "&lt;" in raw and raw.count("&lt;") > raw.count("<"):
        raw = html.unescape(raw)
    return raw


def html_to_text(raw: str, formatted: bool = True, markdown: bool = False, bullet: str = "•") -> str:
    """formatted=False -> plain single-line text; True -> paragraphs, bullets, line breaks.
    markdown=True   -> also keep headings (#), bold (**), italics (*) and links [text](url)."""
    if not raw:
        return ""
    bullet = "-" if markdown else bullet
    soup = BeautifulSoup(unescape_html(raw), "html.parser")
    for t in soup.find_all(SKIP) + soup.find_all(string=lambda s: isinstance(s, Comment)):
        t.extract()

    if not formatted:
        text = re.sub(r"\s+", " ", soup.get_text(" ").replace("\xa0", " ")).strip()
        return re.sub(r"\s+([.,;:!?)])", r"\1", text)

    def walk(node, depth=0):
        if isinstance(node, NavigableString):
            return re.sub(r"\s+", " ", str(node))
        kids = lambda d=depth: "".join(walk(c, d) for c in node.children)  # noqa: E731
        if node.name == "br":
            return "\n"
        if node.name in ("ul", "ol"):
            items = ["\x00" * 2 * depth + (f"{i}." if node.name == "ol" else bullet) + " " + walk(li, depth + 1).strip()
                     for i, li in enumerate(node.find_all("li", recursive=False), 1)]
            return "\n" + "\n".join(items) + "\n\n"
        if node.name in ("td", "th"):
            return kids().strip() + " | "
        inner = kids()
        if markdown and inner.strip():
            pad = lambda x: inner[: len(inner) - len(inner.lstrip())] + x + inner[len(inner.rstrip()):]  # noqa: E731
            if node.name in MD:
                return pad(MD[node.name] + inner.strip() + MD[node.name])
            if node.name == "a" and node.get("href", "").startswith("http"):
                return pad(f"[{inner.strip()}]({node['href']})")
            if node.name[0] == "h" and node.name[1:].isdigit():
                return "\n\n" + "#" * int(node.name[1]) + " " + inner.strip() + "\n\n"
        if node.name in BLOCK and inner.strip():
            gap = "\n" if node.name in ("div", "tr") else "\n\n"
            return gap + inner.strip().rstrip(" |") + ("" if node.name == "tr" else gap)
        return inner

    lines = (re.sub(r" +", " ", l.replace("\xa0", " ")).strip().replace("\x00", " ")
             for l in walk(soup).split("\n"))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
