import json, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re, os

FEEDS = [
    # Phillies
    {"url": "https://philliesnation.com/feed", "team": "phillies", "label": "Phillies Nation"},
    {"url": "https://www.phillies.com/news/rss.xml", "team": "phillies", "label": "Phillies.com"},
    {"url": "https://phillyvoice.com/feed/tag/phillies", "team": "phillies", "label": "PhillyVoice"},
    {"url": "https://www.cbssports.com/rss/headlines/mlb/", "team": "phillies", "label": "CBS Sports MLB"},
    {"url": "https://bleacherreport.com/articles/feed?tag_id=19", "team": "phillies", "label": "Bleacher Report MLB"},

    # Eagles
    {"url": "https://bleedinggreennation.com/rss/index.xml", "team": "eagles", "label": "Bleeding Green Nation"},
    {"url": "https://theeagleswire.usatoday.com/feed", "team": "eagles", "label": "Eagles Wire"},
    {"url": "https://phillyvoice.com/feed/tag/eagles", "team": "eagles", "label": "PhillyVoice Eagles"},
    {"url": "https://www.philadelphiaeagles.com/rss/news_rss.xml", "team": "eagles", "label": "Eagles.com"},
    {"url": "https://www.cbssports.com/rss/headlines/nfl/", "team": "eagles", "label": "CBS Sports NFL"},

    # Sixers
    {"url": "https://libertyballers.com/rss/index.xml", "team": "sixers", "label": "Liberty Ballers"},
    {"url": "https://phillyvoice.com/feed/tag/sixers", "team": "sixers", "label": "PhillyVoice Sixers"},
    {"url": "https://www.cbssports.com/rss/headlines/nba/", "team": "sixers", "label": "CBS Sports NBA"},
    {"url": "https://bleacherreport.com/articles/feed?tag_id=12", "team": "sixers", "label": "Bleacher Report NBA"},

    # Flyers
    {"url": "https://broadstreethockey.com/rss/index.xml", "team": "flyers", "label": "Broad Street Hockey"},
    {"url": "https://phillyvoice.com/feed/tag/flyers", "team": "flyers", "label": "PhillyVoice Flyers"},
    {"url": "https://www.cbssports.com/rss/headlines/nhl/", "team": "flyers", "label": "CBS Sports NHL"},

    # General Philly
    {"url": "https://sportstalkphilly.com/feed", "team": "general", "label": "SportsTalk Philly"},
    {"url": "https://phlsportsnation.com/feed", "team": "general", "label": "PHL Sports Nation"},
    {"url": "https://philasportswire.com/feed", "team": "general", "label": "Philly Sports Wire"},
    {"url": "https://fastphillysports.com/feed", "team": "general", "label": "Fast Philly Sports"},
    {"url": "https://www.inquirer.com/sports/rss.xml", "team": "general", "label": "Philadelphia Inquirer"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/", "team": "general", "label": "NBC Sports Philly"},
]

PHILLY_KEYWORDS = {
    "phillies": ["phillies","harper","nola","wheeler","sanchez","rhys","realmuto","schwarber","stott","turner","citizen","bryce","trea","ranger","orion"],
    "eagles": ["eagles","hurts","sirianni","roseman","devonta","smith","jalen","lincoln financial","nfc east","aj brown","mailata","kelce","kellen"],
    "sixers": ["sixers","76ers","embiid","maxey","george","morey","wells fargo","paul george","edgecombe","nba draft","sixers"],
    "flyers": ["flyers","tortorella","nhl","stanley cup","flyers","samuel ersson"],
}

def detect_team(title, desc, feed_team):
    if feed_team != "general":
        return feed_team
    text = (title + " " + desc).lower()
    for team, keywords in PHILLY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return team
    return "general"

def strip_html(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&#\d+;', '', s)
    return s.strip()

def find_image(item, ns):
    # Try media:thumbnail
    for tag in ['media:thumbnail', '{http://search.yahoo.com/mrss/}thumbnail', '{http://search.yahoo.com/mrss/}content']:
        el = item.find(tag)
        if el is not None:
            url = el.get('url') or el.text
            if url and url.startswith('http'):
                return url
    # Try enclosure
    enc = item.find('enclosure')
    if enc is not None:
        url = enc.get('url', '')
        if url.startswith('http') and any(ext in url for ext in ['.jpg','.jpeg','.png','.webp']):
            return url
    # Parse from description
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
            headers={'User-Agent': 'Mozilla/5.0 BroadStreetSports/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()

        # Parse namespaces
        ns = {}
        root = ET.fromstring(xml_data)
        items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')

        for item in items[:20]:
            title = strip_html(item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title') or '')
            if not title:
                continue

            link = (item.findtext('link') or
                    (item.find('{http://www.w3.org/2005/Atom}link') or ET.Element('x')).get('href') or '')
            desc = strip_html(item.findtext('description') or
                              item.findtext('{http://www.w3.org/2005/Atom}summary') or
                              item.findtext('{http://www.w3.org/2005/Atom}content') or '')[:220]
            pub = (item.findtext('pubDate') or
                   item.findtext('{http://www.w3.org/2005/Atom}published') or
                   item.findtext('{http://www.w3.org/2005/Atom}updated') or '')
            author = strip_html(item.findtext('author') or
                                item.findtext('{http://purl.org/dc/elements/1.1/}creator') or '')
            img = find_image(item, ns)
            team = detect_team(title, desc, feed['team'])

            articles.append({
                'title': title,
                'description': desc,
                'link': link,
                'pubDate': pub,
                'author': author,
                'thumbnail': img,
                'team': team,
                'source': feed['label'],
            })
    except Exception as e:
        print(f"  Failed {feed['label']}: {e}")
    return articles

def main():
    print(f"Fetching news — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    all_articles = []
    for feed in FEEDS:
        print(f"  Fetching {feed['label']}...")
        articles = fetch_feed(feed)
        all_articles.extend(articles)
        print(f"    Got {len(articles)} articles")

    # Sort by date
    def parse_date(d):
        for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S GMT',
                    '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ']:
            try:
                return datetime.strptime(d.strip(), fmt).timestamp()
            except:
                pass
        return 0

    all_articles.sort(key=lambda a: parse_date(a['pubDate']), reverse=True)

    # Deduplicate by title
    seen = set()
    unique = []
    for a in all_articles:
        key = a['title'][:60].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(a)

    print(f"\nTotal unique articles: {len(unique)}")

    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'count': len(unique),
        'articles': unique
    }

    with open('news.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(unique)} articles to news.json")

if __name__ == '__main__':
    main()
