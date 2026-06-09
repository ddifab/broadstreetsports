import json, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re

# ── ESPN API TEAM IDs ──
ESPN_TEAMS = {
    'phillies': {'league': 'mlb',  'id': '22',  'abbr': 'PHI'},
    'eagles':   {'league': 'nfl',  'id': '21',  'abbr': 'PHI'},
    'sixers':   {'league': 'nba',  'id': '20',  'abbr': 'PHI'},
    'flyers':   {'league': 'nhl',  'id': '4',   'abbr': 'PHI'},
}

HEADERS = {'User-Agent': 'Mozilla/5.0 BroadStreetSports/1.0'}

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def fetch_team_scores(team_key):
    t = ESPN_TEAMS[team_key]
    league = t['league']
    team_id = t['id']
    url = f'https://site.api.espn.com/apis/site/v2/sports/{league_path(league)}/teams/{team_id}/schedule'
    try:
        data = fetch_json(url)
        events = data.get('events', [])
        recent, upcoming = [], []
        now = datetime.now(timezone.utc)

        for event in events:
            try:
                date_str = event.get('date', '')
                game_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                competitions = event.get('competitions', [{}])
                comp = competitions[0]
                competitors = comp.get('competitors', [])
                status = comp.get('status', {}).get('type', {})
                status_name = status.get('name', '')
                status_desc = status.get('description', '')
                is_completed = status.get('completed', False)

                home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
                away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
                if not home or not away:
                    continue

                home_abbr = home.get('team', {}).get('abbreviation', '?')
                away_abbr = away.get('team', {}).get('abbreviation', '?')
                home_logo = home.get('team', {}).get('logo', '')
                away_logo = away.get('team', {}).get('logo', '')
                home_score = home.get('score', '')
                away_score = away.get('score', '')

                game = {
                    'date': game_date.strftime('%-m/%-d'),
                    'home': home_abbr,
                    'away': away_abbr,
                    'homeLogo': home_logo,
                    'awayLogo': away_logo,
                    'league': league.upper(),
                    'name': event.get('name', ''),
                    'shortName': event.get('shortName', ''),
                }

                if is_completed:
                    game['scores'] = {home_abbr: int(home_score or 0), away_abbr: int(away_score or 0)}
                    game['status'] = 'final'
                    recent.append((game_date, game))
                elif game_date > now:
                    game['time'] = game_date.strftime('%-I:%M %p')
                    game['status'] = 'scheduled'
                    # Check if live
                    if 'IN_PROGRESS' in status_name or 'in progress' in status_desc.lower():
                        game['status'] = 'live'
                        if home_score and away_score:
                            game['scores'] = {home_abbr: int(home_score), away_abbr: int(away_score)}
                        game['statusDetail'] = status_desc
                    upcoming.append((game_date, game))

            except Exception as e:
                continue

        recent.sort(key=lambda x: x[0], reverse=True)
        upcoming.sort(key=lambda x: x[0])
        return {
            'recent': [g for _, g in recent[:5]],
            'upcoming': [g for _, g in upcoming[:6]],
        }
    except Exception as e:
        print(f"  Error fetching {team_key}: {e}")
        return {'recent': [], 'upcoming': []}

def league_path(league):
    paths = {'mlb': 'baseball/mlb', 'nfl': 'football/nfl', 'nba': 'basketball/nba', 'nhl': 'hockey/nhl'}
    return paths.get(league, league)

def fetch_all_scores():
    print("Fetching live scores from ESPN...")
    scores = {}
    for team_key in ESPN_TEAMS:
        print(f"  {team_key}...")
        scores[team_key] = fetch_team_scores(team_key)
        print(f"    Recent: {len(scores[team_key]['recent'])} | Upcoming: {len(scores[team_key]['upcoming'])}")
    return scores

# ── NEWS FEEDS ──
FEEDS = [
    {"url": "https://philliesnation.com/feed",                       "team": "phillies", "label": "Phillies Nation"},
    {"url": "https://www.phillies.com/news/rss.xml",                 "team": "phillies", "label": "Phillies.com"},
    {"url": "https://phillyvoice.com/feed/tag/phillies",             "team": "phillies", "label": "PhillyVoice"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/tag/phillies","team": "phillies", "label": "NBC Sports Philly"},
    {"url": "https://bleedinggreennation.com/rss/index.xml",         "team": "eagles",   "label": "Bleeding Green Nation"},
    {"url": "https://theeagleswire.usatoday.com/feed",               "team": "eagles",   "label": "Eagles Wire"},
    {"url": "https://phillyvoice.com/feed/tag/eagles",               "team": "eagles",   "label": "PhillyVoice Eagles"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/tag/eagles", "team": "eagles",   "label": "NBC Sports Philly"},
    {"url": "https://libertyballers.com/rss/index.xml",              "team": "sixers",   "label": "Liberty Ballers"},
    {"url": "https://phillyvoice.com/feed/tag/sixers",               "team": "sixers",   "label": "PhillyVoice Sixers"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/tag/76ers",  "team": "sixers",   "label": "NBC Sports Philly"},
    {"url": "https://sixerswire.usatoday.com/feed",                  "team": "sixers",   "label": "Sixers Wire"},
    {"url": "https://broadstreethockey.com/rss/index.xml",           "team": "flyers",   "label": "Broad Street Hockey"},
    {"url": "https://phillyvoice.com/feed/tag/flyers",               "team": "flyers",   "label": "PhillyVoice Flyers"},
    {"url": "https://flyerswire.usatoday.com/feed",                  "team": "flyers",   "label": "Flyers Wire"},
    {"url": "https://sportstalkphilly.com/feed",                     "team": "general",  "label": "SportsTalk Philly"},
    {"url": "https://phlsportsnation.com/feed",                      "team": "general",  "label": "PHL Sports Nation"},
    {"url": "https://philasportswire.com/feed",                      "team": "general",  "label": "Philly Sports Wire"},
    {"url": "https://www.inquirer.com/sports/rss.xml",               "team": "general",  "label": "Philadelphia Inquirer"},
    {"url": "https://www.nbcsportsphiladelphia.com/feed/",           "team": "general",  "label": "NBC Sports Philly"},
    {"url": "https://yardbarker.com/philadelphia_sports/rss",        "team": "general",  "label": "Yardbarker Philly"},
]

PHILLY_REQUIRED = [
    "philadelphia","philly","phillies","eagles","sixers","76ers","flyers",
    "embiid","maxey","hurts","sirianni","roseman","harper","nola","wheeler",
    "sanchez","schwarber","realmuto","stott","trea turner","bryce","devonta",
    "aj brown","a.j. brown","mailata","paul george","morey","tortorella",
    "broad street","lincoln financial","citizens bank","wells fargo center","novacare",
]

DRAMA_KEYWORDS = [
    "drama","beef","feud","called out","fired","quit","rant","blasts","rips",
    "destroys","slams","heated","controversy","suspended","fined","arrested",
    "furious","angry","demand","trade","cut","released","benched","fight",
    "brawl","ejected","investigation","accused","shocking","stunning","wild",
    "insane","explosive","hot take","should be","fire","hire","worst","best ever",
    "greatest","legend","elite","overrated","underrated","frustration",
    "disappointing","collapse","meltdown","comeback","miracle","historic",
    "record","milestone","emotional","heartbreaking","devastating","clutch","choke",
]

def is_philly_relevant(title, desc):
    text = (title + " " + desc).lower()
    return any(kw in text for kw in PHILLY_REQUIRED)

def drama_score(title, desc):
    text = (title + " " + desc).lower()
    return min(sum(1 for kw in DRAMA_KEYWORDS if kw in text), 10)

def strip_html(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    for old, new in [('&amp;','&'),('&nbsp;',' '),('&#\d+;',''),('&lt;','<'),('&gt;','>')]:
        s = re.sub(old, new, s)
    return re.sub(r'\s+', ' ', s).strip()

def find_image(item):
    for tag in ['{http://search.yahoo.com/mrss/}thumbnail','{http://search.yahoo.com/mrss/}content']:
        el = item.find(tag)
        if el is not None:
            url = el.get('url','')
            if url.startswith('http'): return url
    enc = item.find('enclosure')
    if enc is not None:
        url = enc.get('url','')
        if url.startswith('http'): return url
    desc = item.findtext('description') or ''
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if m and m.group(1).startswith('http'): return m.group(1)
    return None

def detect_team(title, desc, feed_team):
    if feed_team != 'general': return feed_team
    text = (title + ' ' + desc).lower()
    kws = {
        'phillies': ['phillies','harper','nola','wheeler','sanchez','schwarber','realmuto','stott','citizens bank'],
        'eagles':   ['eagles','hurts','sirianni','roseman','devonta','jalen hurts','aj brown','mailata','lincoln financial'],
        'sixers':   ['sixers','76ers','embiid','maxey','paul george','morey','wells fargo'],
        'flyers':   ['flyers','tortorella','michkov','couturier'],
    }
    for team, keywords in kws.items():
        if any(k in text for k in keywords): return team
    return 'general'

def fetch_feed(feed):
    articles = []
    try:
        req = urllib.request.Request(feed['url'], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
        for item in items[:25]:
            title = strip_html(item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title') or '')
            if not title or len(title) < 10: continue
            desc = strip_html(item.findtext('description') or item.findtext('{http://www.w3.org/2005/Atom}summary') or '')[:250]
            if not is_philly_relevant(title, desc): continue
            link = item.findtext('link') or ''
            pub = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published') or ''
            author = strip_html(item.findtext('author') or item.findtext('{http://purl.org/dc/elements/1.1/}creator') or '')
            img = find_image(item)
            team = detect_team(title, desc, feed['team'])
            articles.append({
                'title': title, 'description': desc, 'link': link,
                'pubDate': pub, 'author': author, 'thumbnail': img,
                'team': team, 'source': feed['label'],
                'dramaScore': drama_score(title, desc),
            })
    except Exception as e:
        print(f"  Failed {feed['label']}: {e}")
    return articles

def parse_date(d):
    for fmt in ['%a, %d %b %Y %H:%M:%S %z','%a, %d %b %Y %H:%M:%S GMT','%Y-%m-%dT%H:%M:%S%z','%Y-%m-%dT%H:%M:%SZ']:
        try: return datetime.strptime(d.strip(), fmt).timestamp()
        except: pass
    return 0

def fetch_all_news():
    print(f"\nFetching news from {len(FEEDS)} feeds...")
    all_articles = []
    for feed in FEEDS:
        print(f"  {feed['label']}...")
        articles = fetch_feed(feed)
        all_articles.extend(articles)
        if articles: print(f"    {len(articles)} Philly articles")

    all_articles.sort(key=lambda a: (-a.get('dramaScore', 0), -parse_date(a.get('pubDate', ''))))
    seen = set()
    unique = []
    for a in all_articles:
        key = a['title'][:70].lower().strip()
        if key and key not in seen:
            seen.add(key)
            a.pop('dramaScore', None)
            unique.append(a)

    print(f"\n✅ {len(unique)} unique Philly articles")
    return unique

def main():
    now = datetime.now(timezone.utc).isoformat()
    print(f"=== Broad Street Sports Update ===")
    print(f"Time: {now}\n")

    # Fetch scores
    scores = fetch_all_scores()
    with open('scores.json', 'w') as f:
        json.dump({'updated': now, 'scores': scores}, f, indent=2)
    print("✅ Saved scores.json")

    # Fetch news
    articles = fetch_all_news()
    with open('news.json', 'w') as f:
        json.dump({'updated': now, 'count': len(articles), 'articles': articles}, f, indent=2)
    print("✅ Saved news.json")

if __name__ == '__main__':
    main()
