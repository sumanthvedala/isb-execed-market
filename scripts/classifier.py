#!/usr/bin/env python3
"""The rules that file a programme under one theme and topic.

scripts/classify.py runs these over every catalogue row; scripts/check_classification.py
tests them. Every decision carries a reason (`why`), written to programmes_tagged.csv.

The order, first match wins:
  1. data/overrides.csv, hand-checked against the programme's page
  2. a C-suite title ("Chief AI Officer") is filed under the function it teaches
  3. a sector qualifier ("... for Healthcare") wins over a wrapper phrase
  4. the SUBJECT of the title: the main title before any colon or dash, with the
     wrapper ("Executive Programme in ...") and an era qualifier ("... in the Age
     of AI") taken off. Topics whose keywords match it are the candidates; the one
     whose keywords cover the most of the subject wins, then key topics break ties.
  5. the same on the whole title
  6. the title's DOMAIN (finance, marketing, AI, leadership ...): the best topic in
     that theme by the programme's key topics, else the domain's default topic
  7. key topics alone, then the school's category
Keywords match whole words only: "ai" never matches inside "maintain", "port" never
inside "sports". Keywords live in scripts/build_taxonomy.py.
"""
import csv, re, unicodedata, collections, pathlib

R = pathlib.Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- text
_DASH = re.compile('[\u2010-\u2015\u2212]')


def norm(s):
    """lower case, accents off, UK spelling, "artificial intelligence" -> "ai", plurals in -ies
    folded, so a keyword and a title meet on the same spelling"""
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = _DASH.sub(' - ', s).replace('\u2019', "'").replace('\u2018', "'").lower()
    s = re.sub(r'(?<=[a-z]{3})iz(e|ed|es|ing|ation|ations|er|ers)\b', r'is\1', s)
    s = re.sub(r'(?<=[a-z]{2})yz(e|ed|es|ing)\b', r'ys\1', s)
    s = re.sub(r'behavior(?!u)', 'behaviour', s)
    s = re.sub(r'\blabor(?!u)', 'labour', s)
    s = re.sub(r'\bdefense\b', 'defence', s)
    s = re.sub(r'\bprogram(s?)\b', r'programme\1', s)
    s = re.sub(r'(?<=[a-z0-9])-(?=[a-z0-9])', ' ', s)    # business-to-business = business to business
    s = re.sub(r'artificial intelligence|intelligence artificielle', 'ai', s)
    s = re.sub(r'\baiml\b', 'ai ml', s)
    s = re.sub(r'\b(\w{3,})ies\b', r'\1y', s)            # strategies -> strategy
    return re.sub(r'\s+', ' ', s).strip()


def compile_kw(kw):
    """A taxonomy keyword as a whole-word pattern. A keyword starts at a word start;
    it ends at a word end when its last word is short (an acronym, "lean", "port"),
    and is a stem otherwise ("sustainab", "digitis"). ".*" stays inside one phrase."""
    k = norm(kw)
    if not k:
        return None
    k = re.sub(r'(?<![a-z\\])(ai|hr|hrm|ml)(?![a-z])', r'\\b\1\\b', k)
    k = re.sub(r'\((?!\?)', '(?:', k)                  # the keyword's own groups do not capture
    k = k.replace('.*', r'([^;:|]{0,50})')             # a gap: the only capturing group
    last = re.search(r'([a-z0-9&]+)[^a-z0-9&]*$', k)
    closed = last is not None and len(last.group(1)) <= 4
    return re.compile(r'(?<![a-z0-9])(?:' + k + r')' + (r'(?:s|es)?(?![a-z0-9])' if closed else ''))


def strip_brackets(s):
    return re.sub(r'\s+', ' ', re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', s)).strip()


# "... in the Age of AI", "... for the AI Era", "... in Times of AI", "... in a VUCA World":
# the setting, not the subject
_CONTEXT = re.compile(
    r'\s*\b(?:in|for|during|across)\s+(?:the|an?)\s+(?:age|era|times?|world)\s+of\s+[^,;]+'
    r'|\s*\b(?:in|for)\s+(?:the|an?)\s+(?:[\w-]+\s+){1,2}(?:era|age|world)\b'
    r'|\s*\bin\s+times\s+of\s+[^,;]+'
    r'|\s*\bfor\s+the\s+new\s+era\b')
_ERA_AI = re.compile(r'\bai\b|\bgen ?ai\b|generative|agentic|digital|analytic|data')
# "Executive Programme in X", "Masterclass for X", "Professional Certificate Programme in X"
_WRAP = re.compile(r'^(.*?)\b(?:programme|certificate|course|masterclass|master class|diploma|bootcamp|'
                   r'sprint|academy|seminar|workshop)s?\s+(?:in|on|for)\s+(.+)$')
# the words a wrapper may carry before it: "Advanced Management Programme in X" is about X,
# "Finance Master Class for Business Leadership" is about finance
_WRAP_WORDS = set('executive advanced professional post graduate postgraduate pg certificate certified global senior '
                  'general international online blended management leadership development strategic integrated '
                  'accelerated comprehensive the a an of education iim iima iimb iimc iimi iimk iiml isb insead imd '
                  'hbs lbs and & - executive-education programme course young emerging new future'.split())
# "... for Leaders", "... for Managers": who it is for, not what it teaches
_AUDIENCE_WORDS = (r'(?:the\s+)?(?:(?:senior|business|future|new|young|emerging|corporate|enterprise|technology|top|'
                   r'middle|mid-level|first-time)\s+)*(?:leaders|managers|executives|cxos|professionals|decision makers)')
_AUDIENCE = re.compile(r'\s+for\s+' + _AUDIENCE_WORDS + r'\b')
_AUDIENCE_ONLY = re.compile(r'^' + _AUDIENCE_WORDS + r'$')


def parse_title(name):
    """(subject, full title, era) of a programme name, all normalised. The subject is the
    main title (before ':' or ' - ') with the wrapper and the era qualifier taken off."""
    full = strip_brackets(norm(name))
    main = re.split(r'\s*(?::|\s-\s|\|)\s*', full)[0].strip() or full
    era = ''
    m = _CONTEXT.search(main)
    if m:
        era = m.group(0).strip()
        main = (main[:m.start()] + ' ' + main[m.end():]).strip()
    w = _WRAP.match(main)
    subject = main
    if w and set(re.findall(r"[a-z0-9&'-]+", w.group(1))) <= _WRAP_WORDS and not _AUDIENCE_ONLY.match(w.group(2)):
        subject = w.group(2).strip()
    a = _AUDIENCE.search(subject)
    if a and a.start() > 0:
        subject = re.sub(r'\s+', ' ', subject[:a.start()] + ' ' + subject[a.end():]).strip()
    return subject, full, era


def core(subject):
    """what comes before "for" or "with": in "Storytelling for Authentic Leadership" the
    programme teaches storytelling; in "Analytics for Problem Solving", analytics"""
    return re.split(r'\s+(?:for|with)\s+', subject, 1)[0]


# ---------------------------------------------------------------- fixed rules
# A CHRO programme teaches HR; a CFO programme teaches finance. Primary = the
# function taught, secondary = the C-suite ladder.
LADDER = "Becoming a C-suite officer (role-specific ladders)"
OFFICER = [
    (r'\bchro\b|chief human resource|human resources officer', "CHRO and HR leadership"),
    (r'\bcfo\b|chief financ\w* officer', "Corporate finance and capital allocation"),
    (r'chief ai officer|\bcaio\b|chief product & ai|chief product and ai|chief \w+ and ai officer|'
     r'chief technology and ai|\bctaio\b|^ai officer', "AI strategy for the enterprise"),
    (r'\bcdaio\b|chief digital', "Enterprise digital transformation strategy and roadmaps"),
    (r'\bcto\b|chief technology officer|\bcio\b|chief information officer',
     "Enterprise digital transformation strategy and roadmaps"),
    (r'\bcmo\b|chief marketing|chief growth and marketing|chief growth & marketing', "Marketing strategy for executives"),
    (r'\bcso\b|chief strategy officer', "Corporate strategy, portfolio and diversification"),
    (r'\bcoo\b|chief operating|chief operations', "Operational excellence and process improvement"),
    (r'\bcro\b|chief revenue officer', "Sales leadership and sales force management"),
    (r'chief product officer|\bcpo\b', "Product management and product marketing"),
    (r'chief legal officer', "Compliance, ethics and integrity programmes"),
    (r'\bceo\b|chief executive officer|owner/president|president/ceo', "CEO / top management leadership"),
]
_AI_OFFICER = re.compile(r'\bai\b|\bcaio\b|\bctaio\b|\bcdaio\b|digital')

# "Advanced Management Programme for Healthcare" is a healthcare programme
SECTOR = [
    (r'for healthcare|in healthcare|healthcare management', "Healthcare strategy, payers and providers"),
    (r'for infrastructure|infrastructure management', "Infrastructure, construction and real estate development"),
    (r'for manufacturing|manufacturing management', "Manufacturing strategy and Industry 4.0 operations"),
    (r'for banking|banking management|\bbfsi\b', "Banking, financial services and insurance sector management"),
]

# The title's domain, most specific first: the theme a programme belongs to when its
# title names no topic, and the topic it takes when its key topics name none either.
DOMAINS = [
    (r'\bboards?\b|boardroom|non.executive|independent director|\bdirectors?\b|conseils? d.administration|'
     r'gouvernance|administrateur', "Board effectiveness and director duties"),
    (r'health|hospital|clinical|pharma|medical|patient|life science', "Hospital and healthcare operations management"),
    (r'sustainab|\besg\b|climate|net.zero|carbon|\bgreen\b|environmental', "Sustainability and ESG strategy for the enterprise"),
    (r'\binvest|wealth|asset management|asset allocation|security (?:industry|market|analysis)|portfolio management',
     "Investment management and portfolio theory"),
    (r'fintech|financ|accounting|\binvest|banking|\bbank\b|wealth|treasury|valuation|capital market|\bcredit\b|'
     r'insurance|actuar|\baudit|\btax', "Finance for non-finance managers"),
    (r'\bhr\b|\bhrm\b|human resource|\btalent|people manag|workforce|compensation|recruit|\bl&d\b|'
     r'learning and development|industrial relation|labour law', "Strategic HR and business partnering"),
    (r'supply chain|logistic|procure|purchas|operations|operational|\bquality\b|\blean\b|six sigma|'
     r'project manag|warehous|manufactur|\bscm\b|service excellence', "Operational excellence and process improvement"),
    (r'product manag|\bproducts?\b', "Product management and product marketing"),
    (r'\bsales\b|\bselling', "Sales leadership and sales force management"),
    (r'marketing|\bbrand|customer|consumer|pricing|\bretail', "Marketing strategy for executives"),
    (r'cyber|information security', "Cybersecurity strategy for leaders and boards"),
    (r'\bai\b|\bia\b|\bgen ?ai\b|generative|agentic|machine learning|\bml\b|deep learning|neural|\bllms?\b',
     "AI and machine learning fundamentals for executives"),
    (r'analytic|\bdata\b|data science|business intelligence|quantitative|statistic|decision science',
     "Business analytics for decision-making"),
    (r'digital|technolog|\bit\b|cloud|automation|\btech\b|information system',
     "Enterprise digital transformation strategy and roadmaps"),
    (r'public polic|public system|public sector|government|\bpolicy\b|civil serv|public administration|'
     r'smart cit|public value', "Public policy design and analysis"),
    (r'family business|family enterprise|family owned|families in business|family in business|business famil|family firm',
     "Family business succession and next-generation owners"),
    (r'entrepreneur|start.?up|\bventure|founder|\bmsme\b|\bsme\b|small business', "Starting and scaling a venture"),
    (r'innovat|design thinking|creativ', "Innovation strategy and portfolio"),
    (r'governance|gouvernance|complian|\blaws?\b|\blegal|\brisk\b|regulat|ethic|integrity', "Enterprise risk management"),
    (r'negotiat|deal.?making', "Negotiation for commercial outcomes"),
    (r'communicat|presentation|speak|storytell|writing|persuas|etiquette|personality|presence|articulat',
     "Public speaking, presentation and boardroom communication"),
    (r'influenc|networking|career', "Networking, influence and career strategy"),
    (r'decision', "Decision-making, biases and behavioural judgment"),
    (r'thinking|problem.solving', "Critical thinking and problem solving"),
    (r'wellbeing|well-being|stress|burnout|resilien|mindful', "Personal resilience, wellbeing and burnout"),
    (r'emotional|self.awareness', "Emotional intelligence and self-awareness"),
    (r'productiv|time management|effectiveness', "Time, attention and personal productivity"),
    (r'\bcoach', "Coaching and the leader as coach"),
    (r'\bteams?\b|teamwork|team building', "Leading high-performing teams"),
    (r'\bculture|organisational behaviour|high.performance organi', "Organisational culture and culture change"),
    (r'\bchange\b|\btransformation\b|turnaround', "Leading change and transformation"),
    (r'uncertain|vuca|volatil|crisis|disrupt|extreme environment', "Leading in uncertainty, volatility and ambiguity"),
    (r'\bstrateg(?:y|ie)\b|strategic management|strategist', "Competitive strategy and advantage"),
    (r'merger|acquisition|\bm&a\b', "M&A strategy and deal rationale"),
    (r'econom', "Macroeconomics for executives"),
    (r'neuroscience|\bbrain\b', "Decision-making, biases and behavioural judgment"),
    (r'silicon valley|innovation ecosystem|immersion', "Innovation strategy and portfolio"),
    (r'general management|business management|executive development|management programme|management development|executive management|'
     r'business administration|management essentials|mini.mba|business acumen|management accelerat|'
     r'management foundation|management excellence', "General management programmes for senior leaders"),
    (r'\bchief\b|c.suite|\bcxos?\b', LADDER),
    (r'senior executive|senior leader|top management|\bceo', "CEO / top management leadership"),
    (r'first.time manager|new manager|young leader|emerging leader|early career', "Transition to leadership / first-time manager"),
    (r'\blead|\bmanager|managerial', "Leadership styles and situational leadership"),
    (r'\bmanag', "General management programmes for senior leaders"),
]
FALLBACK_TOPICS = {t for _, t in DOMAINS}
# Broad topics: a title that also names a specific topic is filed under the specific one
GENERIC = {"Leadership styles and situational leadership", "Mini-MBA and business fundamentals for specialists"}
# Themes that are a skill or a level rather than a subject. When a title's subject is AI
# and it also names one of these ("Gen AI, Agentic Systems & Intelligent Decision-making"),
# it is an AI programme. A function ("AI in Marketing", "HRM in Times of AI") keeps its theme.
SKILL_THEMES = {"Personal Effectiveness & Communication", "Leadership & Executive Capability",
                "General Management (Integrative)", "Strategy"}
_AI_TITLE = re.compile(r'\bai\b|\bia\b|\bgen ?ai\b|generative|agentic|machine learning|\bllms?\b')
AI_THEME = "AI, Data & Digital"
# words that make an AI title about leading people rather than about the technology
PEOPLE_WORDS = re.compile(r'\bteams?\b|workforce|workplace|employee|\bpeople\b|\bmanag|human|organi[sz]ation')
AI_DEFAULT = "AI and machine learning fundamentals for executives"

# Out of scope: faculty development, academic audiences, degree programmes (CATALOGUE_SPEC)
_FACULTY = re.compile(r'faculty development|case teaching|case writing|case pedagog|doctoral|'
                      r'participant-centered learning|participant centred learning|research and academic publishing|'
                      r'teaching effectiveness|for teachers|teacher training|malaviya mission|'
                      r'management development programme for faculty', re.I)
_DEGREE = re.compile(r'\bmaster of\b|\bmasters? in\b|(?<!mini )(?<!mini-)\be?mba\b|\bpgpx\b', re.I)
_MOOC = re.compile(r'coursera|\bedx\b|edx\.org|^iimbx', re.I)

WEIGHT = {'key_topics': 1.0, 'school_category': 0.6, 'target_audience': 0.3}


class Classifier:
    def __init__(self, base=R):
        self.tax = list(csv.DictReader(open(base / 'data' / 'taxonomy.csv', encoding='utf-8')))
        self.T = {t['topic_id']: t for t in self.tax}
        self.byname = {t['topic']: t['topic_id'] for t in self.tax}
        self.order = {t['topic_id']: i for i, t in enumerate(self.tax)}
        self.kw = []                                    # (topic_id, pattern, keyword)
        for t in self.tax:
            for k in t['keywords'].split(';'):
                p = compile_kw(k)
                if p:
                    self.kw.append((t['topic_id'], p, k.strip()))
        self.req = {t['topic_id']: re.compile(t['requires']) for t in self.tax if t.get('requires')}
        named = [n for _, n in OFFICER + SECTOR + DOMAINS] + [LADDER, AI_DEFAULT,
                                                            "AI governance frameworks and operating models"]
        bad = [n for n in named if n not in self.byname]
        assert not bad, f"rules name topics that are not in the taxonomy: {bad}"
        self.officer = [(re.compile(p), self.byname[n]) for p, n in OFFICER]
        self.sector = [(re.compile(p), self.byname[n]) for p, n in SECTOR]
        self.domains = [(re.compile(r'(?<![a-z0-9])(?:' + p + ')'), self.byname[n]) for p, n in DOMAINS]
        self.generic = {self.byname[n] for n in GENERIC}
        self.overrides, self.override_sec = [], {}
        f = base / 'data' / 'overrides.csv'
        if f.exists():
            for r in csv.DictReader(open(f, encoding='utf-8')):
                k = (r['school_slug'].strip(), r['name_contains'].strip().lower())
                assert r['topic'].strip() in self.byname, f"override topic not in taxonomy: {r['topic']}"
                self.overrides.append((*k, self.byname[r['topic'].strip()]))
                if (r.get('secondary_topic') or '').strip():
                    assert r['secondary_topic'].strip() in self.byname, f"override secondary not in taxonomy: {r}"
                    self.override_sec[k] = self.byname[r['secondary_topic'].strip()]

    # ------------------------------------------------------------ helpers
    def theme(self, tid):
        return self.T[tid]['theme'] if tid in self.T else ''

    def hits(self, text):
        """topic -> (characters of the text its keywords cover, keywords matched)"""
        spans, kws = collections.defaultdict(set), collections.defaultdict(list)
        if not text:
            return {}
        for tid, p, k in self.kw:
            if tid in self.req and not self.req[tid].search(text):
                continue
            for m in p.finditer(text):
                cov = set(range(m.start(), m.end()))
                for g in range(1, (m.re.groups or 0) + 1):
                    if m.start(g) >= 0:
                        cov -= set(range(m.start(g), m.end(g)))
                spans[tid].update(cov)
                if k not in kws[tid]:
                    kws[tid].append(k)
        return {t: (len(spans[t]), kws[t]) for t in spans}

    def field_scores(self, r):
        sc = collections.Counter()
        for f, w in WEIGHT.items():
            for tid, (_, ks) in self.hits(norm(r.get(f))).items():
                sc[tid] += w * len(ks)
        return sc

    def domain(self, *texts):
        for t in texts:
            for p, tid in self.domains:
                m = p.search(t)
                if m:
                    return tid, m.group(0)
        return None, ''

    def excluded(self, r):
        nm, cat = r.get('programme_name') or '', r.get('school_category') or ''
        if _FACULTY.search(' '.join([nm, cat, r.get('target_audience') or ''])):
            return 'faculty or academic programme'
        if _DEGREE.search(nm + ' ' + cat):
            return 'degree programme'
        if _MOOC.search(' '.join(str(r.get(k, '')) for k in ('partner', 'url', 'programme_name'))):
            return 'MOOC marketplace'
        return ''

    # ------------------------------------------------------------ the decision
    def classify(self, r, use_overrides=True):
        """dict(topic_id, secondary_topic_id, confidence, why)"""
        name = r.get('programme_name') or ''
        sl = r.get('school_slug', '')
        subject, full, era = parse_title(name)
        ai_title = bool(_AI_TITLE.search(full))
        res = lambda tid, sec, conf, why: dict(topic_id=tid, secondary_topic_id=sec if sec != tid else '',
                                               confidence=conf, why=why)

        if use_overrides:
            low = name.lower()
            for sch, frag, tid in self.overrides:
                if sch == sl and frag in low:
                    sec = self.override_sec.get((sch, frag), '')
                    if not sec:
                        sec = self._officer_sec(full) or ''
                    return res(tid, sec, 'override', f'override "{frag}"')

        for p, tid in self.officer:
            if p.search(full):
                return res(tid, self._officer_sec(full), 'officer-rule', f'C-suite title: {p.search(full).group(0)}')
        for p, tid in self.sector:
            if p.search(full):
                return res(tid, '', 'sector-rule', f'sector: {p.search(full).group(0)}')

        fs = self.field_scores(r)
        dom, dword = self.domain(subject, full)
        cdom, _ = self.domain(core(subject))
        sh, th, ch = self.hits(subject), self.hits(full), self.hits(core(subject))

        def rank(cands):
            # specific before broad; then most of the core subject covered; then the core's domain;
            # then most of the subject, of the title; then key topics; then the title's domain
            return sorted(cands, key=lambda t: (t in self.generic, -ch.get(t, (0,))[0],
                                                bool(cdom) and self.theme(t) != self.theme(cdom),
                                                -sh.get(t, (0,))[0], -th.get(t, (0,))[0], -fs.get(t, 0),
                                                self.theme(t) != self.theme(dom), self.order[t]))

        def second(primary, pool):
            rest = [t for t in pool if t != primary]
            if ai_title and self.theme(primary) != AI_THEME:
                ai = [t for t in rest if self.theme(t) == AI_THEME]
                return ai[0] if ai else self.byname[AI_DEFAULT]
            return rest[0] if rest else ''

        if sh or th:
            ranked = rank(set(sh) | set(th) | {t for t, v in fs.items() if v >= 1})
            pool = [t for t in ranked if t in sh]
            if not pool:      # the subject names no topic: rank what the whole title names by the title
                pool = sorted([t for t in ranked if t in th], key=lambda t: (
                    t in self.generic, -th[t][0], -fs.get(t, 0), self.theme(t) != self.theme(dom), self.order[t]))
            top = pool[0]
            ai_subject = bool(_AI_TITLE.search(subject))
            if ai_subject and self.theme(top) in SKILL_THEMES and not (
                    self.T[top]['ai_era_flag'] == 'New' and PEOPLE_WORDS.search(subject)):
                ai = [t for t in pool if self.theme(t) == AI_THEME]
                top = ai[0] if ai else top
            where, kws = ('subject', sh[top][1]) if top in sh else ('title', th[top][1])
            conf = 'high' if where == 'subject' else 'medium'
            return res(top, second(top, ranked), conf, f'{where} "{subject if where == "subject" else full}": {", ".join(kws)}')

        if dom:
            dth = self.theme(dom)
            inside = [t for t, v in fs.most_common() if v >= 1 and self.theme(t) == dth]
            ranked = rank(set(fs))
            if inside:
                top = rank(inside)[0]
                return res(top, second(top, ranked), 'low', f'domain "{dword}" -> {dth}; key topics')
            return res(dom, second(dom, ranked), 'fallback', f'domain "{dword}" -> {dth}; no topic named')

        if fs:
            ranked = rank(set(fs))
            if fs[ranked[0]] >= 1:
                return res(ranked[0], second(ranked[0], ranked), 'low', 'key topics only')
        cdom, cword = self.domain(norm(r.get('school_category')))
        if cdom:
            return res(cdom, '', 'fallback', f'school category "{cword}"')
        return res('', '', 'none', 'nothing matched')

    def _officer_sec(self, full):
        for p, _ in self.officer:
            if p.search(full):
                return self.byname["AI governance frameworks and operating models"] if _AI_OFFICER.search(full) \
                    else self.byname[LADDER]
        return ''
