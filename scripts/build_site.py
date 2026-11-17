#!/usr/bin/env python3
"""Turns the dashboard template into a standalone static page for GitHub Pages.

Two differences from the Claude-artifact version:
  1. It is a complete HTML document. The artifact host injects a doctype, head
     and a small CSS reset at publish time; a static host does not.
  2. The data is fetched from data.json at runtime instead of being inlined, so
     the scheduled refresh rewrites one small JSON file and never touches the
     page. That is what makes the page cacheable and the diff readable.
"""
import pathlib, sys, re, urllib.parse

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
    '<div style="padding:16px;font:14px system-ui;color:#192890">' +
    'Could not load data.json. If you have just deployed, wait for the Pages build to finish. ' +
    '(' + String(err) + ')</div>');
  console.error(err);
});
</script>''', body_part.rstrip(), count=1)

RESET = """<style>
  /* the artifact host supplies this; a static host does not */
  :root{color-scheme:light}
  *,*::before,*::after{box-sizing:border-box}
  body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif;background:#FFFFFF}
  img{max-width:100%}
  [hidden]{display:none!important}
</style>"""

# Fonts live in site/fonts/ and are served from there, so the page never depends on a
# third-party font host. Inter (the variable "Inter V", SIL Open Font License) is the text
# face. Reckless (Displaay, licensed) is the heading face. Files can be .woff2, .woff, .otf
# or .ttf, and a variable file (name contains "GX" or "variable") covers every weight. A
# static Reckless file needs its weight in its name (Reckless-Regular, -Medium, -Bold ...).
# Not served: macOS "._" metadata files, and any file with "trial" in its name, because a
# foundry's trial font is licensed for evaluation, not for a public website. With no
# Reckless file, headings use the fallback in the template's --serif stack.
WEIGHTS = [('heavy', 900), ('black', 900), ('semibold', 600), ('demibold', 600), ('bold', 700), ('medium', 500),
           ('light', 300), ('regular', 400), ('book', 400)]
FORMAT = {'.woff2': 'woff2', '.woff': 'woff', '.otf': 'opentype', '.ttf': 'truetype'}
MIME = {'.woff2': 'font/woff2'}
FONTDIR = ROOT / 'site' / 'fonts'
files = sorted(FONTDIR.glob('*')) if FONTDIR.is_dir() else []
for f in files:
    if f.name.startswith('._') or f.suffix.lower() not in FORMAT:
        continue
    if 'trial' in f.name.lower():
        print(f'skipped {f.name}: a trial font is not licensed for a public site')


def usable(f, family):
    n = f.name.lower()
    return family in n and not n.startswith('._') and 'trial' not in n and f.suffix.lower() in FORMAT


def face(family, weight, style, fs):
    order = list(FORMAT)
    src = ','.join("url(fonts/%s) format('%s')" % (urllib.parse.quote(x.name), FORMAT[x.suffix.lower()])
                   for x in sorted(fs, key=lambda x: order.index(x.suffix.lower())))
    return "@font-face{font-family:%s;font-weight:%s;font-style:%s;font-display:swap;src:%s}" % (family, weight, style, src)


css, preload = [], []
inter = [f for f in files if usable(f, 'inter')]
if inter:
    css.append(face('"Inter V"', '100 900', 'normal', inter))
    preload += [f for f in inter if f.suffix.lower() == '.woff2'][:1]
faces = {}
for f in files:
    if not usable(f, 'reckless'):
        continue
    n = f.name.lower()
    if 'gx' in n or 'variable' in n:
        w = '100 900'
    else:
        w = str(next((v for k, v in WEIGHTS if k in n), 400))
    faces.setdefault((w, 'italic' if 'italic' in n else 'normal'), []).append(f)
for (w, st), fs in sorted(faces.items()):
    css.append(face('Reckless', w, st, fs))
    preload += [f for f in fs if f.suffix.lower() == '.woff2'][:1]
FONTS = ''
if css:
    FONTS = '\n'.join('<link rel="preload" as="font" type="font/woff2" crossorigin href="fonts/%s">' % urllib.parse.quote(f.name)
                      for f in preload) + '\n<style>\n' + '\n'.join(css) + '\n</style>'
print('Inter: %s | Reckless: %s' % ('site/fonts' if inter else 'not found, system sans',
      f'{len(faces)} face(s) from site/fonts' if faces else 'not found, headings use the fallback serif'))

# the ISB logo, when the brand team has supplied one for a dark ground
for name in ('logo.svg', 'logo.png'):
    if (ROOT / 'site' / 'brand' / name).exists():
        body_part = body_part.replace('<b>ISB</b>', f'<img src="brand/{name}" alt="ISB">', 1)
        print(f'logo: site/brand/{name}')
        break

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="ISB Executive Education's view of the market: every programme, price and new launch at 15 other business schools and 4 platforms.">
{RESET}
{FONTS}
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
