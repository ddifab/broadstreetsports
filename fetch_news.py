import json, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re

# ── FEEDS — Philly-specific sources only, no general national feeds ──
FEEDS = [
    # Phillies — dedicated Philly sources
    {"url": "https://philliesnation.com/feed",                    "team": "phillies", "label": "Phillies Nation"},
    {"url": "https://www.phillies.com/news/rss.xml",              "team": "phillies", "label": "Phillies.com"},
    {"url": "https://phillyvoice.com/feed/tag/phillies",          "team": "phillies", "label": "PhillyVoice"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/tag/phillies", "team": "phillies", "label": "NBC Sports Philly"},
    {"url": "https://theathletic.com/mlb/philadelphia-phillies/feed/", "team": "phillies", "label": "The Athletic"},

    # Eagles — dedicated Philly sources
    {"url": "https://bleedinggreennation.com/rss/index.xml",      "team": "eagles",   "label": "Bleeding Green Nation"},
    {"url": "https://theeagleswire.usatoday.com/feed",            "team": "eagles",   "label": "Eagles Wire"},
    {"url": "https://phillyvoice.com/feed/tag/eagles",            "team": "eagles",   "label": "PhillyVoice Eagles"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/tag/eagles", "team": "eagles", "label": "NBC Sports Philly"},
    {"url": "https://www.philadelphiaeagles.com/rss/news_rss.xml","team": "eagles",   "label": "Eagles.com"},

    # Sixers — dedicated Philly sources
    {"url": "https://libertyballers.com/rss/index.xml",           "team": "sixers",   "label": "Liberty Ballers"},
    {"url": "https://phillyvoice.com/feed/tag/sixers",            "team": "sixers",   "label": "PhillyVoice Sixers"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/tag/76ers","team": "sixers",   "label": "NBC Sports Philly"},
    {"url": "https://sixerswire.usatoday.com/feed",               "team": "sixers",   "label": "Sixers Wire"},

    # Flyers — dedicated Philly sources
    {"url": "https://broadstreethockey.com/rss/index.xml",        "team": "flyers",   "label": "Broad Street Hockey"},
    {"url": "https://phillyvoice.com/feed/tag/flyers",            "team": "flyers",   "label": "PhillyVoice Flyers"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/tag/flyers","team": "flyers",  "label": "NBC Sports Philly"},
    {"url": "https://flyerswire.usatoday.com/feed",               "team": "flyers",   "label": "Flyers Wire"},

    # General Philly sports — drama, opinions, talk radio energy
    {"url": "https://sportstalkphilly.com/feed",                  "team": "general",  "label": "SportsTalk Philly"},
    {"url": "https://phlsportsnation.com/feed",                   "team": "general",  "label": "PHL Sports Nation"},
    {"url": "https://philasportswire.com/feed",                   "team": "general",  "label": "Philly Sports Wire"},
    {"url": "https://fastphillysports.com/feed",                  "team": "general",  "label": "Fast Philly Sports"},
    {"url": "https://www.inquirer.com/sports/rss.xml",            "team": "general",  "label": "Philadelphia Inquirer"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/",        "team": "general",  "label": "NBC Sports Philly"},
    {"url": "https://yardbarker.com/philadelphia_sports/rss",     "team": "general",  "label": "Yardbarker Philly"},
]

# ── PHILLY KEYWORD FILTERS ──
# For general feeds, articles MUST contain at least one of these to be included
# This prevents random national sports news from slipping in
PHILLY_REQUIRED = [
    "philadelphia", "philly", "phillies", "eagles", "sixers", "76ers",
    "flyers", "embiid", "maxey", "hurts", "sirianni", "roseman",
    "harper", "nola", "wheeler", "sanchez", "schwarber", "realmuto",
    "stott", "trea turner", "bryce", "devonta", "jalen hurts",
    "aj brown", "a.j. brown", "mailata", "paul george", "morey",
    "tortorella", "broad street", "lincoln financial", "citizens bank",
    "wells fargo center", "novacare", "south philly"
]

# Team-specific keywords for classification
TEAM_KEYWORDS = {
    "phillies": ["phillies","harper","nola","wheeler","sanchez","sánchez",
                 "rhys hoskins","realmuto","schwarber","stott","trea","ranger suarez",
                 "orion kerkering","citizens bank park","red october","bryce"],
    "eagles":   ["eagles","hurts","sirianni","roseman","devonta smith","jalen hurts",
                 "aj brown","a.j. brown","mailata","kelce","kellen moore",
                 "lincoln financial","nfc east","fly eagles fly"],
    "sixers":   ["sixers","76ers","embiid","maxey","paul george","morey",
                 "wells fargo center","joel embiid","tyrese maxey",
                 "vj edgecombe","nba draft","process"],
    "flyers":   ["flyers","tortorella","nhl","wells fargo center","broad street bullies",
                 "samuel ersson","matvei michkov","sean couturier"],
}

# ── DRAMA/ENGAGEMENT SCORING ──
# Articles with these words get boosted to the top — this is the clickbait fuel
DRAMA_KEYWORDS = [
    "drama","beef","feud","called out","fired","quit","rant","blasts",
    "rips","destroys","slams","heated","controversy","suspended","fined",
    "arrested","furious","angry","demand","trade","cut","released","benched",
    "benching","fight","brawl","ejected","incident","investigation","accused",
    "shocking","stunning","unbelievable","wild","insane","crazy","explosive",
    "hot take","unpopular","should be","need to","must","fire","hire",
    "worst","best ever","greatest","legend","elite","overrated","underrated",
    "frustration","disappointing","collapse","meltdown","comeback","miracle",
    "historic","record","milestone","emotional","tears","incredible",
    "heartbreaking","devastating","clutch","choke","redemption"
]

def is_philly_relevant(title, desc):
    """Return True only if article is actually about a Philly team or player."""
    text = (title + " " + desc).lower()
    return any(kw in text for kw in PHILLY_REQUIRED)

def detect_team(title, desc, feed_team):
    if feed_team != "general":
        return feed_team
    text = (title + " " + desc).lower()
    for team, keywords in TEAM_KEYWORDS.items():
        if any(k in text for k in keywords):
            return team
    return "general"

def drama_score(title, desc):
    """Score 0-10 based on drama/engagement potential."""
    text = (title + " " + desc).lower()
    score = sum(1 for kw in DRAMA_KEYWORDS if kw in text)
    return min(score, 10)

def strip_html(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&#\d+;', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def find_image(item):
    for tag in [
        'media:thumbnail',
        '{http://search.yahoo.com/mrss/}thumbnail',
        '{http://search.yahoo.com/mrss/}content',
        '{http://www.w3.org/2005/Atom}link',
    ]:
        el = item.find(tag)
        if el is not None:
            url = el.get('url') or el.get('href') or el.text
            if url and url.startswith('http') and any(
                ext in url.lower() for ext in ['.jpg','.jpeg','.png','.webp','.gif']
            ):
                return url
    enc = item.find('enclosure')
    if enc is not None:
        url = enc.get('url', '')
        if url.startswith('http'):
            return url
    desc = item.findtext('description') or ''
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if m and m.group(1).startswith('http'):
        return m.group(1)
    return None

def fetch_feed(feed):
    articles = []
    try:
        req = urllib.request.Request(
            feed['url'],
            headers={
                'User-Agent': 'Mozilla/5.0 BroadStreetSports/1.0',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*'
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')

        for item in items[:25]:
            title = strip_html(
                item.findtext('title') or
                item.findtext('{http://www.w3.org/2005/Atom}title') or ''
            )
            if not title or len(title) < 10:
                continue

            desc = strip_html(
                item.findtext('description') or
                item.findtext('{http://www.w3.org/2005/Atom}summary') or
                item.findtext('{http://www.w3.org/2005/Atom}content') or ''
            )[:250]

            # FILTER — skip anything not Philly-relevant
            if not is_philly_relevant(title, desc):
                continue

            link = (
                item.findtext('link') or
                (item.find('{http://www.w3.org/2005/Atom}link') or ET.Element('x')).get('href') or ''
            )
            pub = (
                item.findtext('pubDate') or
                item.findtext('{http://www.w3.org/2005/Atom}published') or
                item.findtext('{http://www.w3.org/2005/Atom}updated') or ''
            )
            author = strip_html(
                item.findtext('author') or
                item.findtext('{http://purl.org/dc/elements/1.1/}creator') or ''
            )
            img = find_image(item)
            team = detect_team(title, desc, feed['team'])
            score = drama_score(title, desc)

            articles.append({
                'title': title,
                'description': desc,
                'link': link,
                'pubDate': pub,
                'author': author,
                'thumbnail': img,
                'team': team,
                'source': feed['label'],
                'dramaScore': score,
            })

    except Exception as e:
        print(f"  Failed {feed['label']}: {e}")
    return articles

def parse_date(d):
    for fmt in [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S GMT',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%a, %d %b %Y %H:%M:%S +0000',
    ]:
        try:
            return datetime.strptime(d.strip(), fmt).timestamp()
        except:
            pass
    return 0

def main():
    print(f"Fetching Philly sports news — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    all_articles = []

    for feed in FEEDS:
        print(f"  Fetching {feed['label']} ({feed['team']})...")
        articles = fetch_feed(feed)
        all_articles.extend(articles)
        print(f"    Got {len(articles)} Philly-relevant articles")

    # Sort: drama score first, then by date
    all_articles.sort(key=lambda a: (
        -a.get('dramaScore', 0),
        -parse_date(a.get('pubDate', ''))
    ))

    # Deduplicate by title
    seen = set()
    unique = []
    for a in all_articles:
        key = a['title'][:70].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(a)

    # Remove dramaScore from output (internal use only)
    for a in unique:
        a.pop('dramaScore', None)

    print(f"\n✅ Total unique Philly articles: {len(unique)}")
    teams = {}
    for a in unique:
        teams[a['team']] = teams.get(a['team'], 0) + 1
    for t, c in sorted(teams.items()):
        print(f"   {t}: {c}")

    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'count': len(unique),
        'articles': unique
    }

    with open('news.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to news.json")

if __name__ == '__main__':
    main()
