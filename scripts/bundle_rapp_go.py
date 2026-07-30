#!/usr/bin/env python3
"""Re-port kody-w/rapp-static-apis' rapp-go into one self-contained HTML app.

Upstream rapp-go is a multi-file PWA; this repo requires single-file apps, so the
whole ES module graph is inlined behind a tiny registry: each module body becomes
a function that receives a `__req` resolver and returns its export object, which
keeps module scopes isolated (no name collisions) and evaluates in import order.

    git clone https://github.com/kody-w/rapp-static-apis /tmp/rapp-static-apis
    python3 scripts/bundle_rapp_go.py /tmp/rapp-static-apis apps/games-puzzles/rapp-go.html

Both arguments are optional; the defaults are the paths above. If upstream renames
a symbol that PATCHES or HTML_PATCHES anchors on, the build fails loudly rather
than emitting a silently broken app.
"""
import os
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rapp-static-apis"
OUT = sys.argv[2] if len(sys.argv) > 2 else "apps/games-puzzles/rapp-go.html"

ENTRY = "rapp-go/index.html"

# ── module source patches applied before parsing ──────────────────────────────
PATCHES = {
    "rapp-go/catch.js": [
        # `import.meta` is a syntax error outside a real module body; the guard
        # above it already short-circuits in a browser (no `process`).
        ("const u = import.meta.url.split('/').pop();", "const u = '';"),
    ],
    "companion/twin.mjs": [
        ("_qrMod = await import('../track/qr.mjs');", "_qrMod = __req('track/qr.mjs');"),
        ("_qrMod = await import('/track/qr.mjs');", "_qrMod = __req('track/qr.mjs');"),
    ],
    "rapp-go/onboard.js": [
        # Never hard-code a deploy path: derive the share base from where we run.
        ("const PAGES_URL = 'https://kody-w.github.io/rapp-static-apis/rapp-go/';",
         "const PAGES_URL = (typeof location !== 'undefined' ? location.origin + location.pathname : '');"),
    ],
    "rapp-go/lib/nav.js": [
        # The sibling rapps (companion/hologram/lantern) are separate apps and are
        # not part of this single-file port: show them as not-landed, like journal.
        ("{ key: 'map',     glyph: '\u25c8', label: 'map',     href: r => `${r}/rapp-go/index.html` },",
         "{ key: 'map',     glyph: '\u25c8', label: 'map',     href: () => null },"),
        ("{ key: 'twin',    glyph: '\u25cd', label: 'twin',    href: r => `${r}/companion/index.html` },",
         "{ key: 'twin',    glyph: '\u25cd', label: 'twin',    href: () => null },"),
        ("{ key: 'basket',  glyph: '\u25cf', label: 'basket',  href: r => `${r}/hologram/index.html` },",
         "{ key: 'basket',  glyph: '\u25cf', label: 'basket',  href: () => null },"),
        ("{ key: 'lantern', glyph: '\u25cb', label: 'lantern', href: r => `${r}/lantern/index.html` },",
         "{ key: 'lantern', glyph: '\u25cb', label: 'lantern', href: () => null },"),
        # the active room must never be dimmed as unavailable
        ("if (href) a.href = href + demoSuffix; else a.className = 'off';",
         "if (href) a.href = href + demoSuffix; else if (room.key !== active) a.className = 'off';"),
    ],
}

META = """<meta name="description" content="A quiet, no-backend Pokemon-Go-like explorer: a hand-rolled canvas slippy map over real OpenStreetMap places, with genome-driven creatures spawned from the live sky where you actually stand.">
<meta name="rappterzoo:author" content="kody-w">
<meta name="rappterzoo:author-type" content="human">
<meta name="rappterzoo:category" content="games_puzzles">
<meta name="rappterzoo:tags" content="geolocation,map,canvas,pwa,procedural,creature-collector,local-first">
<meta name="rappterzoo:type" content="game">
<meta name="rappterzoo:complexity" content="advanced">
<meta name="rappterzoo:created" content="2026-07-30">
<meta name="rappterzoo:generation" content="1">
<meta name="rappterzoo:license" content="see kody-w/rapp-static-apis">
<!--
  rapp-go — ported from https://github.com/kody-w/rapp-static-apis (rapp-go/).
  Upstream is a multi-file PWA; this is a single-file build for localFirstTools:
  the whole ES module graph (tilemap, spawn, catch, poi, onboard, lib/*, plus
  companion/twin.mjs, companion/genetics.mjs and track/qr.mjs) is inlined below
  behind a tiny module registry, and the pieces that cannot survive on their own
  are dropped: the service worker + web manifest (separate files) and the doors
  into the sibling rapps (companion / hologram / lantern), which are distinct
  apps and are not part of this port.
-->"""

# ── whole-page patches for the standalone build ───────────────────────────────
HTML_PATCHES = [
    # separate files that a single-file app cannot ship
    ('<link rel="manifest" href="manifest.webmanifest">\n', ""),
    ('<link rel="apple-touch-icon" href="icon-180.png">\n', ""),
    ("""if ('serviceWorker' in navigator) {
  try {
    navigator.serviceWorker.register('./sw.js');
    navigator.serviceWorker.addEventListener('message', e => {
      if (!e.data || e.data.type !== 'rapp-update-ready') return;
      updateReady = true;
      refreshChips();
    });
  } catch {}
}
""", "// (single-file build: no service worker — sw.js is a separate file)\n"),
    # doors into sibling rapps that are not part of this port
    ("""        <a class="act" id="door-talk" target="_blank" rel="noopener">talk</a>
        <a class="act" id="door-breed" target="_blank" rel="noopener">breed</a>
""", ""),
    ("""  $('door-talk').href = DEMO ? talkHref(rec.egg).replace('index.html#','index.html?demo=1#') : talkHref(rec.egg);
  $('door-breed').href = DEMO ? breedHref(rec.egg).replace('index.html#','index.html?demo=1#') : breedHref(rec.egg);
  $('door-keep').href = '../hologram/index.html' + (DEMO ? '?demo=1' : '') + '#kept=' + encodeURIComponent(rec.id);
  $('door-keep').textContent = '◍ view this keepsake';
""", "  // (single-file build: the talk / breed / keepsake doors lead to sibling rapps)\n"),
    # provenance + discovery metadata
    ('<title>rapp·go — catch the sky where you stand</title>',
     '<title>rapp·go — catch the sky where you stand</title>\n' + META),
]

IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def patch(key, src):
    for old, new in PATCHES.get(key, []):
        if old not in src:
            raise SystemExit("patch target missing in %s:\n  %s" % (key, old))
        src = src.replace(old, new)
    return src


def resolve(spec, from_key):
    base = os.path.dirname(from_key)
    return os.path.normpath(os.path.join(base, spec)).replace(os.sep, "/")


IMPORT_RE = re.compile(
    r"^[ \t]*import\s+(?P<clause>[^;]*?)\s+from\s+['\"](?P<spec>[^'\"]+)['\"]\s*;?[ \t]*$",
    re.M | re.S,
)


def rewrite_imports(src, key, deps):
    """Turn static imports into `__req` destructuring, recording dependencies."""

    def sub(m):
        clause = m.group("clause").strip()
        target = resolve(m.group("spec"), key)
        deps.append(target)
        req = "__req(%r)" % target
        if clause.startswith("*"):  # import * as ns from '...'
            ns = clause.split(" as ", 1)[1].strip()
            return "const %s = %s;" % (ns, req)
        if clause.startswith("{"):  # import { a, b as c } from '...'
            inner = clause.strip()[1:-1]
            parts = []
            for piece in inner.split(","):
                piece = piece.strip()
                if not piece:
                    continue
                if " as " in piece:
                    orig, alias = [p.strip() for p in piece.split(" as ")]
                    parts.append("%s: %s" % (orig, alias))
                else:
                    parts.append(piece)
            return "const { %s } = %s;" % (", ".join(parts), req)
        # default import (possibly with a named group after it)
        if "," in clause:
            dflt, rest = clause.split(",", 1)
            return "const %s = %s.default; const %s = %s;" % (
                dflt.strip(), req, rest.strip().replace("{", "{ ").replace("}", " }"), req)
        return "const %s = %s.default;" % (clause, req)

    return IMPORT_RE.sub(sub, src)


def scan_declarator_names(src, i):
    """Collect identifiers bound by a declarator list starting at index i."""
    names = []
    depth = 0
    expect = True
    n = len(src)
    while i < n:
        c = src[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth < 0:
                break
        elif c in "'\"`":
            quote, i = c, i + 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    break
                i += 1
        elif depth == 0 and c == ";":
            break
        elif depth == 0 and c == ",":
            expect = True
        elif depth == 0 and c == "\n":
            # a newline at depth 0 after a completed declarator ends the statement
            # only if the next non-space char starts a new statement; ASI is rare
            # in this codebase, so keep scanning until ';'.
            pass
        elif expect and (c.isalpha() or c in "_$"):
            m = IDENT.match(src, i)
            names.append(m.group(0))
            i = m.end()
            expect = False
            continue
        i += 1
    return names


EXPORT_DECL = re.compile(r"^[ \t]*export\s+(?=(?:async\s+)?(?:function|class|const|let|var)\b)", re.M)
EXPORT_LIST = re.compile(r"^[ \t]*export\s*\{(?P<names>[^}]*)\}\s*;?[ \t]*$", re.M)
EXPORT_DEFAULT = re.compile(r"^[ \t]*export\s+default\s+", re.M)


def strip_exports(src):
    names = []

    # export { a, b as c };
    def sub_list(m):
        for piece in m.group("names").split(","):
            piece = piece.strip()
            if not piece:
                continue
            if " as " in piece:
                orig, alias = [p.strip() for p in piece.split(" as ")]
                names.append((alias, orig))
            else:
                names.append((piece, piece))
        return ""

    src = EXPORT_LIST.sub(sub_list, src)

    # export default <expr>;
    has_default = False
    if EXPORT_DEFAULT.search(src):
        has_default = True
        src = EXPORT_DEFAULT.sub(lambda m: m.group(0).replace("export default", "const __default =")
                                 .replace("export  default", "const __default ="), src)
        src = src.replace("export default ", "const __default = ")

    # export <decl>
    out = []
    pos = 0
    for m in EXPORT_DECL.finditer(src):
        out.append(src[pos:m.start()])
        rest = src[m.end():]
        indent = m.group(0)[: len(m.group(0)) - len(m.group(0).lstrip())]
        out.append(indent)
        decl = re.match(r"(async\s+)?(function\s*\*?|class|const|let|var)\s+", rest)
        kind = decl.group(2).split()[0]
        if kind in ("function", "class"):
            nm = IDENT.match(rest, decl.end())
            names.append((nm.group(0), nm.group(0)))
        else:
            for nm in scan_declarator_names(rest, decl.end()):
                names.append((nm, nm))
        pos = m.end()
    out.append(src[pos:])
    src = "".join(out)

    seen, uniq = set(), []
    for alias, orig in names:
        if alias in seen:
            continue
        seen.add(alias)
        uniq.append((alias, orig))
    return src, uniq, has_default


def build_module(key):
    with open(os.path.join(SRC, key), encoding="utf-8") as fh:
        src = fh.read()
    src = patch(key, src)
    deps = []
    src = rewrite_imports(src, key, deps)
    src, names, has_default = strip_exports(src)
    fields = ["%s: %s" % (alias, orig) if alias != orig else alias for alias, orig in names]
    if has_default:
        fields.append("default: __default")
    body = "__def(%r, function (__req) {\n%s\nreturn { %s };\n});" % (key, src.strip("\n"), ", ".join(fields))
    return body, deps, [a for a, _ in names]


def main():
    with open(os.path.join(SRC, ENTRY), encoding="utf-8") as fh:
        html = fh.read()

    # ── walk the import graph from the entry page's module script ────────────
    m = re.search(r'<script type="module">\n(.*?)\n</script>', html, re.S)
    if not m:
        raise SystemExit("entry module script not found")
    entry_src = m.group(1)
    entry_deps = []
    entry_src = rewrite_imports(entry_src, ENTRY, entry_deps)

    modules, order, exports = {}, [], {}
    queue = list(entry_deps)
    while queue:
        key = queue.pop(0)
        if key in modules:
            continue
        body, deps, names = build_module(key)
        modules[key] = body
        exports[key] = names
        order.append(key)
        queue.extend(deps)

    runtime = (
        "/* ---- inlined module registry (single-file build) ---- */\n"
        "const __M = Object.create(null), __C = Object.create(null);\n"
        "function __def(k, f) { __M[k] = f; }\n"
        "function __req(k) {\n"
        "  if (k in __C) return __C[k];\n"
        "  const f = __M[k];\n"
        "  if (!f) throw new Error('inlined module not found: ' + k);\n"
        "  return (__C[k] = f(__req));\n"
        "}\n"
    )
    bundle = runtime + "\n" + "\n\n".join(modules[k] for k in order) + "\n\n" + \
        "/* ---- page ---- */\n" + entry_src
    html = html[: m.start(1)] + bundle + html[m.end(1):]

    for old, new in HTML_PATCHES:
        if old not in html:
            raise SystemExit("html patch target missing:\n  %s" % old[:90])
        html = html.replace(old, new, 1)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)

    print("modules inlined (%d):" % len(order))
    for k in order:
        print("  %-28s %2d exports" % (k, len(exports[k])))
    print("wrote %s (%d bytes)" % (OUT, len(html)))


if __name__ == "__main__":
    main()
