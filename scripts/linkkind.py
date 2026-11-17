#!/usr/bin/env python3
"""What kind of page a link opens, judged from the URL alone.

One definition, used by build_data.py (which links a programme's name only to
its own page) and link_audit.py (which queues every other kind for the second
pass of the refresh). Nothing here fetches anything.

    page        the programme's own page at the school or its delivery partner
    brochure    a PDF or other document
    news        a press release, newsroom item, blog post or media article
    aggregator  a course-listing site that is not the school or its partner
    index       a home page, catalogue index or course calendar
    shortener   a redirect whose destination cannot be read from the URL
    private     a sign-in link (SharePoint, OneDrive, Google Docs)
    broken      not a web address at all (a bare file name, for instance)
    none        blank
"""
import re
import urllib.parse

AGGREGATORS = re.compile(
    r'shiksha|careers360|collegedunia|collegedekho|riseupp|iimjobs|coursereport|careervira|scribd|'
    r'classcentral|mooc-list|getmyuni|jagranjosh', re.I)
NEWS_HOSTS = re.compile(
    r'theweek\.in|thehansindia|economictimes|indiatimes|business-standard|livemint|thehindu|hindustantimes|'
    r'indianexpress|financialexpress|moneycontrol|ndtv|indiatoday|businesstoday|prnewswire|businesswire|'
    r'globenewswire|aninews|ptinews|businessworld|bweducation|educationtimes|edexlive|deccanchronicle|'
    r'telegraphindia|tribuneindia|forbes|reuters|bloomberg|(^|\.)ft\.com|linkedin\.com|medium\.com|'
    r'youtube\.com|youtu\.be|twitter\.com|(^|\.)x\.com|facebook\.com|instagram\.com|wikipedia\.org', re.I)
# a path SEGMENT that says the page is editorial, not a programme. Whole
# segments only: "/news/..." is news, "/newscience/" and "/insight-series/" are not.
NEWS_PATH = re.compile(
    r'(^|/)(news|newsroom|news-and-events|news-events|press|press-releases?|pressroom|media-cent(re|er)|'
    r'blogs?|stor(y|ies)|articles?|announcements?|wire-updates|in-the-news|latest-news|magazine)(/|$)', re.I)
SHORTENERS = re.compile(r'^(www\.)?(tinyurl\.com|bit\.ly|t\.co|goo\.gl|lnkd\.in|rb\.gy|shorturl\.at|cutt\.ly|ow\.ly)$', re.I)
PRIVATE = re.compile(r'sharepoint\.com|onedrive\.live|1drv\.ms|docs\.google\.com|drive\.google\.com', re.I)
DOCS = re.compile(r'\.(pdf|docx?|pptx?|xlsx?)$', re.I)
INDEX_PATHS = {'', 'index.php', 'index.html', 'en', 'programmes', 'programs', 'courses', 'partner-programmes',
               'for-individuals', 'executive-education', 'view-all-programs', 'all-programs'}
INDEX_PATH = re.compile(r'course-calend[ae]r|programme-calendar|program-calendar|universities-and-institutes/[^/]+$', re.I)

LABEL = {'page': 'programme page', 'brochure': 'brochure', 'news': 'launch article', 'aggregator': 'course listing',
         'index': 'catalogue page', 'shortener': 'short link', 'private': 'sign-in link', 'broken': 'broken link',
         'none': ''}
# what the second pass has to do about each kind that is not the programme's own page
FIX = {'news': 'a news article, not the programme page',
       'aggregator': 'a course-listing site, not the school or its partner',
       'index': 'a home page, catalogue index or calendar, not one programme',
       'shortener': 'a short link; replace it with the address it lands on',
       'private': 'a sign-in link; the dashboard is public',
       'broken': 'not a web address',
       'brochure': 'a brochure, not a page',
       'none': 'no link held'}


def kind(u):
    u = (u or '').strip()
    if not u:
        return 'none'
    if not re.match(r'https?://', u, re.I):
        return 'broken'
    p = urllib.parse.urlparse(u)
    host, path = p.netloc.lower(), p.path
    if SHORTENERS.match(host):
        return 'shortener'
    if PRIVATE.search(host):
        return 'private'
    if DOCS.search(path):
        return 'brochure'
    if AGGREGATORS.search(host):
        return 'aggregator'
    if NEWS_HOSTS.search(host) or NEWS_PATH.search(path):
        return 'news'
    if path.strip('/').lower() in INDEX_PATHS or INDEX_PATH.search(path):
        return 'index'
    return 'page'
