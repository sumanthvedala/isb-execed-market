#!/usr/bin/env python3
"""Turns the dashboard template into a standalone static page for GitHub Pages.

Two differences from the Claude-artifact version:
  1. It is a complete HTML document. The artifact host injects a doctype, head
     and a small CSS reset at publish time; a static host does not.
  2. The data is fetched from data.json at runtime instead of being inlined, so
     the scheduled refresh rewrites one small JSON file and never touches the
     page. That is what makes the page cacheable and the diff readable.
"""
import pathlib, sys, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
tpl = (ROOT / 'site' / 'dashboard.tpl.html').read_text(encoding='utf-8')

SPLIT = '<header class="top">'
if SPLIT not in tpl:
    sys.exit('template shape changed: no <header class="top"> found')
head_part, body_part = tpl.split(SPLIT, 1)
body_part = SPLIT + body_part

# the page must not carry a build-time data blob
if '__DATA__' not in tpl:
    sys.exit('template has no __DATA__ placeholder to replace with the fetch')
body_part = body_part.replace(
    'const D = __DATA__;',
    "const D = await (await fetch('data.json', {cache: 'no-store'})).json();", 1)

# every top-level IIFE in the template reads D, so the whole script becomes the
# body of one async function and D is awaited once at the top of it.
body_part = body_part.replace('<script>', '<script>\n(async () => {\n', 1)
body_part = re.sub(r'</script>\s*$', '''
})().catch(err => {
  document.body.insertAdjacentHTML('afterbegin',
    '<div style="padding:16px;font:14px system-ui;color:#7E1B2E">' +
    'Could not load data.json. If you have just deployed, wait for the Pages build to finish. ' +
    '(' + String(err) + ')</div>');
  console.error(err);
});
</script>''', body_part.rstrip(), count=1)

RESET = """<style>
  /* the artifact host supplies this; a static host does not */
  :root{color-scheme:light}
  *,*::before,*::after{box-sizing:border-box}
  body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif;background:#FBF9F8}
  img{max-width:100%}
  [hidden]{display:none!important}
</style>"""

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="ISB Executive Education portfolio against 15 peer schools and 4 platforms: where to lead, follow, defend, deepen or diversify.">
{RESET}
{head_part.strip()}
</head>
<body>
{body_part}
</body>
</html>
"""
out = ROOT / 'site' / 'index.html'
out.write_text(doc, encoding='utf-8')
print(f'wrote {out} ({len(doc):,} bytes)')
