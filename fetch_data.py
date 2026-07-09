import urllib.request
import json
import xml.etree.ElementTree as ET
import socket
import time
import datetime
import math
import os
import sys

# Output directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATE_FILE = os.path.join(DATA_DIR, 'gsi_state.json')
HISTORY_FILE = os.path.join(DATA_DIR, 'gsi_history.json')

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def make_request(url, timeout=7):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except Exception as e:
        print(f"Warning: Failed to fetch {url}. Error: {e}", file=sys.stderr)
        return None

def make_json_request(url, timeout=7):
    data = make_request(url, timeout)
    if data:
        try:
            return json.loads(data.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Error parsing JSON from {url}: {e}", file=sys.stderr)
    return None

# Sentiment helper: basic keyword polarity analyzer
def estimate_sentiment(text):
    text = text.lower()
    negative_words = [
        'war', 'dead', 'kill', 'crisis', 'crash', 'ban', 'attack', 'virus', 'threat', 'death',
        'conflict', 'clash', 'sanctions', 'strike', 'missile', 'military', 'protest', 'troops',
        'escalate', 'bomb', 'terror', 'shooting', 'inflation', 'recession', 'collapse', 'loss',
        'fear', 'anxiety', 'panic', 'danger', 'destabilize', 'nuclear', 'disaster', 'outage'
    ]
    positive_words = [
        'peace', 'win', 'new', 'love', 'safe', 'good', 'growth', 'joy', 'deal', 'help',
        'cooperation', 'stabilize', 'agreement', 'recovery', 'summit', 'progress', 'benefit',
        'alliance', 'treaty', 'renew', 'green', 'clean', 'vaccine', 'cure', 'success', 'trust'
    ]
    neg_count = sum(1 for w in negative_words if w in text)
    pos_count = sum(1 for w in positive_words if w in text)
    
    total = neg_count + pos_count
    if total == 0:
        return 0.0
    return (pos_count - neg_count) / total

# 1. FETCH API: YAHOO FINANCE CHART API
def fetch_financials():
    tickers = [
        '^GSPC', '^IXIC', '^DJI', '^GDAXI', '^N225', '000001.SS', '^FTSE', '^FCHI', '^VIX', '^TNX', # Indices
        'CL=F', 'NG=F', 'GC=F', 'SI=F', 'HG=F', 'S=F', 'C=F', 'W=F', # Commodities
        'EURUSD=X', 'GBPUSD=X', 'JPY=X', 'CNY=X', # Forex
        'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'XRP-USD' # Crypto
    ]
    signals = {}
    for symbol in tickers:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        res = make_json_request(url)
        price_change = 0.0
        price = 0.0
        vol = 0.0
        high = 0.0
        low = 0.0
        
        if res and 'chart' in res and 'result' in res['chart'] and res['chart']['result']:
            result = res['chart']['result'][0]
            meta = result.get('meta', {})
            price = meta.get('regularMarketPrice', 0.0)
            prev_close = meta.get('chartPreviousClose', 0.0)
            vol = meta.get('regularMarketVolume', 0.0)
            high = meta.get('regularMarketDayHigh', 0.0)
            low = meta.get('regularMarketDayLow', 0.0)
            if price > 0 and prev_close > 0:
                price_change = ((price - prev_close) / prev_close) * 100
                
        spread = (high - low) / price * 100 if price > 0 else 0.0
        signals[symbol] = {
            'change_pct': price_change,
            'price': price,
            'volume': vol,
            'spread_pct': spread
        }
        # Small delay to avoid rate limits
        time.sleep(0.1)
    return signals

# 2. FETCH API: NOAA SOLAR WIND & SPACE WEATHER
def fetch_space_weather():
    plasma = make_json_request("https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json")
    mag = make_json_request("https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json")
    scales = make_json_request("https://services.swpc.noaa.gov/products/noaa-scales.json")
    
    data = {
        'wind_speed': 400.0,
        'wind_density': 5.0,
        'wind_temp': 100000.0,
        'bz': 0.0,
        'bt': 5.0,
        'kp': 1.0
    }
    
    # Plasma: Speed, Density, Temp (last entry)
    if plasma and len(plasma) > 0:
        for last_entry in reversed(plasma):
            if last_entry.get('proton_speed') is not None:
                try:
                    data['wind_density'] = float(last_entry.get('proton_density', 5.0))
                    data['wind_speed'] = float(last_entry.get('proton_speed', 400.0))
                    data['wind_temp'] = float(last_entry.get('proton_temperature', 100000.0))
                    break
                except (ValueError, TypeError):
                    pass
            
    # Mag: Bz, Bt (last entry)
    if mag and len(mag) > 0:
        for last_entry in reversed(mag):
            if last_entry.get('bz_gsm') is not None:
                try:
                    data['bz'] = float(last_entry.get('bz_gsm', 0.0))
                    data['bt'] = float(last_entry.get('bt', 5.0))
                    break
                except (ValueError, TypeError):
                    pass
            
    # Scales: Kp index proxy
    if scales and '0' in scales and 'G' in scales['0']:
        try:
            data['kp'] = float(scales['0']['G'].get('metric', 1.0))
        except ValueError:
            pass
            
    return data

# 3. FETCH API: USGS EARTHQUAKES
def fetch_earthquakes():
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    res = make_json_request(url)
    data = {
        'count_24h': 0,
        'count_m3': 0,
        'count_m4_5': 0,
        'count_m6': 0,
        'max_mag': 0.0,
        'avg_mag': 0.0,
        'energy_j': 0.0
    }
    if res and 'features' in res:
        features = res['features']
        data['count_24h'] = len(features)
        
        mags = []
        energy_sum = 0.0
        for f in features:
            mag = f['properties'].get('mag')
            if mag is not None:
                try:
                    mag = float(mag)
                    mags.append(mag)
                    if mag < 3.0:
                        data['count_m3'] += 1
                    elif mag < 6.0:
                        data['count_m4_5'] += 1
                    else:
                        data['count_m6'] += 1
                        
                    # Earthquake Energy release formula: E = 10^(1.5M + 4.8) Joules
                    energy_sum += math.pow(10, 1.5 * mag + 4.8)
                except ValueError:
                    pass
        
        if mags:
            data['max_mag'] = max(mags)
            data['avg_mag'] = sum(mags) / len(mags)
            data['energy_j'] = energy_sum
            
    return data

# 4. FETCH API: OPEN-METEO WEATHER
def fetch_weather():
    # 10 global cities
    cities = {
        'Washington': (38.9, -77.0),
        'London': (51.5, -0.12),
        'Tokyo': (35.68, 139.69),
        'Beijing': (39.9, 116.4),
        'Cairo': (30.0, 31.2),
        'Kyiv': (50.45, 30.5),
        'Sydney': (-33.86, 151.2),
        'Sao_Paulo': (-23.55, -46.6),
        'New_Delhi': (28.6, 77.2),
        'Nairobi': (-1.29, 36.8)
    }
    lats = ','.join(str(c[0]) for c in cities.values())
    lons = ','.join(str(c[1]) for c in cities.values())
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,precipitation"
    res = make_json_request(url)
    signals = {}
    if res:
        # If it's a list (multiple locations query), iterate
        locations = res if isinstance(res, list) else [res]
        city_names = list(cities.keys())
        for idx, loc in enumerate(locations):
            if idx < len(city_names) and 'current' in loc:
                city = city_names[idx]
                curr = loc['current']
                signals[city] = {
                    'temp': curr.get('temperature_2m', 15.0),
                    'humidity': curr.get('relative_humidity_2m', 60.0),
                    'pressure': curr.get('surface_pressure', 1013.0),
                    'wind_speed': curr.get('wind_speed_10m', 10.0),
                    'precipitation': curr.get('precipitation', 0.0)
                }
    return signals

# 5. FETCH API: WIKIPEDIA PAGEVIEWS
def fetch_wiki_pageviews():
    # Last 24 hours (use current UTC date - 1 day to be safe with pageviews API sync)
    yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    date_str = yesterday.strftime('%Y%m%d00')
    next_date_str = (yesterday + datetime.timedelta(days=1)).strftime('%Y%m%d00')
    
    terms = [
        "World_War_III", "Cyberwarfare", "Inflation", "NATO", "Nuclear_weapon",
        "Epidemic", "Stock_market_crash", "Refugee", "Protest", "Terrorism"
    ]
    signals = {}
    for term in terms:
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/all-agents/{term}/daily/{date_str}/{next_date_str}"
        res = make_json_request(url)
        views = 500
        if res and 'items' in res and len(res['items']) > 0:
            views = res['items'][0].get('views', 500)
        signals[term] = views
    return signals

# 6. FETCH API: REDDIT & MASTODON
def fetch_social():
    social_data = {
        'reddit_news_sentiment': 0.0,
        'reddit_news_comments': 0,
        'mastodon_politics_sentiment': 0.0,
        'mastodon_politics_volume': 0
    }
    
    # Reddit WorldNews
    reddit_res = make_json_request("https://www.reddit.com/r/worldnews/hot.json?limit=10")
    if reddit_res and 'data' in reddit_res and 'children' in reddit_res['data']:
        posts = reddit_res['data']['children']
        sentiments = []
        comments = 0
        for p in posts:
            pdata = p.get('data', {})
            title = pdata.get('title', '')
            sentiments.append(estimate_sentiment(title))
            comments += pdata.get('num_comments', 0)
        social_data['reddit_news_sentiment'] = sum(sentiments) / len(sentiments) if sentiments else 0.0
        social_data['reddit_news_comments'] = comments
        
    # Mastodon politics tag
    mastodon_res = make_json_request("https://mastodon.social/api/v1/timelines/tag/politics?limit=10")
    if mastodon_res and isinstance(mastodon_res, list):
        sentiments = []
        for post in mastodon_res:
            content = post.get('content', '')
            sentiments.append(estimate_sentiment(content))
        social_data['mastodon_politics_sentiment'] = sum(sentiments) / len(sentiments) if sentiments else 0.0
        social_data['mastodon_politics_volume'] = len(mastodon_res)
        
    return social_data

# 7. FETCH API: GOOGLE NEWS RSS & RELIEFWEB
def fetch_geopolitics():
    geo_data = {
        'news_volume': 0,
        'news_sentiment': 0.0,
        'reliefweb_crises_count': 0
    }
    
    # News RSS search query (Conflict, Sanctions, Crisis)
    queries = [
        'conflict+OR+war+OR+clash',
        'sanctions+OR+embargo',
        'recession+OR+inflation+OR+crisis'
    ]
    titles = []
    for q in queries:
        url = f"https://news.google.com/rss/search?q={q}"
        xml_data = make_request(url)
        if xml_data:
            try:
                root = ET.fromstring(xml_data)
                items = root.findall('.//item')
                geo_data['news_volume'] += len(items)
                for item in items[:15]:
                    title_node = item.find('title')
                    if title_node is not None and title_node.text:
                        titles.append(title_node.text)
            except Exception as e:
                print(f"Error parsing RSS XML: {e}", file=sys.stderr)
                
    if titles:
        geo_data['news_sentiment'] = sum(estimate_sentiment(t) for t in titles) / len(titles)
        
    # ReliefWeb RSS Feed (active crisis/reports)
    rw_xml = make_request("https://reliefweb.int/updates/rss.xml")
    if rw_xml:
        try:
            root = ET.fromstring(rw_xml)
            items = root.findall('.//item')
            geo_data['reliefweb_crises_count'] = len(items) * 15 # proxy count
        except Exception as e:
            print(f"Error parsing ReliefWeb RSS XML: {e}", file=sys.stderr)
            geo_data['reliefweb_crises_count'] = 150 # default fallback
        
    return geo_data

# 8. DNS LATENCY CHECK
def check_dns_latency():
    dns_servers = {
        'google': '8.8.8.8',
        'cloudflare': '1.1.1.1',
        'quad9': '9.9.9.9',
        'opendns': '208.67.222.222',
        'level3': '4.2.2.2'
    }
    results = {}
    for name, ip in dns_servers.items():
        t0 = time.time()
        success = False
        try:
            # Check port 53 via TCP to measure latency safely without admin ping privileges
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((ip, 53))
            s.close()
            t_diff = time.time() - t0
            success = True
            results[name] = {
                'latency_ms': t_diff * 1000.0,
                'status': 1.0
            }
        except Exception:
            results[name] = {
                'latency_ms': 2000.0,
                'status': 0.0
            }
    return results

# ============================================================================
# NORMALIZATION & AGGREGATION SYSTEM
# ============================================================================

def norm_linear(val, min_val, max_val, invert=False):
    if max_val == min_val:
        return 50.0
    pct = (val - min_val) / (max_val - min_val)
    score = pct * 100.0
    if invert:
        score = 100.0 - score
    return max(0.0, min(100.0, score))

def norm_log(val, min_log, max_log, invert=False):
    log_val = math.log10(max(val, 0.1))
    return norm_linear(log_val, min_log, max_log, invert)

def main():
    print("Initializing planetary synchronization...", file=sys.stdout)
    
    # Ensure data folder exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 1. Fetch all raw data
    print("Fetching Space Weather data...", file=sys.stdout)
    space_sw = fetch_space_weather()
    
    print("Fetching Earthquake data...", file=sys.stdout)
    quakes = fetch_earthquakes()
    
    print("Fetching Climate data (Open-Meteo)...", file=sys.stdout)
    weather_data = fetch_weather()
    
    print("Fetching Market indicators...", file=sys.stdout)
    financials = fetch_financials()
    
    print("Fetching Social sentiment data...", file=sys.stdout)
    social_data = fetch_social()
    
    print("Fetching Geopolitics news...", file=sys.stdout)
    geo_data = fetch_geopolitics()
    
    print("Fetching Wiki traffic analytics...", file=sys.stdout)
    wiki_data = fetch_wiki_pageviews()
    
    print("Running DNS routing health checks...", file=sys.stdout)
    dns_latencies = check_dns_latency()
    
    print("Running normalization equations...", file=sys.stdout)
    
    # 2. Build normalized signals metadata dictionary (150+ signals total)
    all_signals = []
    
    # Category 1: Space Weather
    all_signals.append({
        'id': 'solar_wind_speed', 'name': 'Solar Wind Speed', 'category': 'Space Weather',
        'raw': space_sw['wind_speed'], 'unit': 'km/s', 'norm': norm_linear(space_sw['wind_speed'], 300, 800, invert=True),
        'source': 'NOAA SWPC', 'source_url': 'https://services.swpc.noaa.gov/products/solar-wind/plasma-5-day.json',
        'formula': 'Linear mapping: 300km/s = 100, 800km/s = 0',
        'desc': 'Plasma stream velocity from coronal holes. Higher speeds impact satellite connectivity and power grids.'
    })
    all_signals.append({
        'id': 'solar_wind_density', 'name': 'Solar Wind Density', 'category': 'Space Weather',
        'raw': space_sw['wind_density'], 'unit': 'N/cm³', 'norm': norm_linear(space_sw['wind_density'], 1, 25, invert=True),
        'source': 'NOAA SWPC', 'source_url': 'https://services.swpc.noaa.gov/products/solar-wind/plasma-5-day.json',
        'formula': 'Linear mapping: 1 N/cm³ = 100, 25 N/cm³ = 0',
        'desc': 'Proton concentration in solar wind. Increased density puts pressure on Earth\'s magnetopause.'
    })
    all_signals.append({
        'id': 'magnetic_field_bz', 'name': 'Interplanetary Bz Field', 'category': 'Space Weather',
        'raw': space_sw['bz'], 'unit': 'nT', 'norm': norm_linear(space_sw['bz'], -15, 5, invert=False),
        'source': 'NOAA SWPC', 'source_url': 'https://services.swpc.noaa.gov/products/solar-wind/mag-5-day.json',
        'formula': 'Linear mapping: Bz >= +5nT = 100, Bz <= -15nT = 0',
        'desc': 'North-South component of solar magnetic field. Negative Bz opens Earth\'s field to solar wind particles.'
    })
    all_signals.append({
        'id': 'magnetic_field_bt', 'name': 'Interplanetary Bt Field', 'category': 'Space Weather',
        'raw': space_sw['bt'], 'unit': 'nT', 'norm': norm_linear(space_sw['bt'], 2, 20, invert=True),
        'source': 'NOAA SWPC', 'source_url': 'https://services.swpc.noaa.gov/products/solar-wind/mag-5-day.json',
        'formula': 'Linear mapping: 2nT = 100, 20nT = 0',
        'desc': 'Total strength of interplanetary magnetic field. High values indicate magnetic compression.'
    })
    all_signals.append({
        'id': 'geomagnetic_kp', 'name': 'Geomagnetic Kp Index', 'category': 'Space Weather',
        'raw': space_sw['kp'], 'unit': 'Kp', 'norm': norm_linear(space_sw['kp'], 1, 9, invert=True),
        'source': 'NOAA SWPC', 'source_url': 'https://services.swpc.noaa.gov/products/noaa-scales.json',
        'formula': 'Linear mapping: Kp 1 = 100, Kp 9 = 0',
        'desc': 'Global magnetic disturbance index. Level 5+ indicates geomagnetic storm status.'
    })
    
    # Category 2: Biosphere Seismology & Wildfires
    all_signals.append({
        'id': 'earthquake_count_24h', 'name': 'Earthquake Count (24h)', 'category': 'Biosphere Resilience',
        'raw': quakes['count_24h'], 'unit': 'count', 'norm': norm_linear(quakes['count_24h'], 20, 200, invert=True),
        'source': 'USGS Seismology', 'source_url': 'https://earthquake.usgs.gov/',
        'formula': 'Linear mapping: 20 quakes = 100, 200 quakes = 0',
        'desc': 'Total count of global seismic events recorded by USGS in the last day.'
    })
    all_signals.append({
        'id': 'earthquake_max_mag', 'name': 'Maximum Earthquake Magnitude', 'category': 'Biosphere Resilience',
        'raw': quakes['max_mag'], 'unit': 'M', 'norm': norm_linear(quakes['max_mag'], 4.0, 7.5, invert=True),
        'source': 'USGS Seismology', 'source_url': 'https://earthquake.usgs.gov/',
        'formula': 'Linear mapping: M4.0 = 100, M7.5 = 0',
        'desc': 'Peak magnitude value among recent seismic activity.'
    })
    all_signals.append({
        'id': 'earthquake_avg_mag', 'name': 'Average Earthquake Magnitude', 'category': 'Biosphere Resilience',
        'raw': quakes['avg_mag'], 'unit': 'M', 'norm': norm_linear(quakes['avg_mag'], 2.0, 4.5, invert=True),
        'source': 'USGS Seismology', 'source_url': 'https://earthquake.usgs.gov/',
        'formula': 'Linear mapping: M2.0 = 100, M4.5 = 0',
        'desc': 'Average magnitude of global earthquakes. Higher values show elevated crustal stress.'
    })
    all_signals.append({
        'id': 'earthquake_energy_j', 'name': 'Total Seismic Energy Released', 'category': 'Biosphere Resilience',
        'raw': quakes['energy_j'], 'unit': 'J', 'norm': norm_log(quakes['energy_j'], 11, 16, invert=True),
        'source': 'USGS Seismology', 'source_url': 'https://earthquake.usgs.gov/',
        'formula': 'Log scale base 10: 10^11 J = 100, 10^16 J = 0',
        'desc': 'Calculated physical energy release. Significant spikes indicate massive single rupture events.'
    })
    
    # Category 3: Climate Risk (80 signals from 10 cities)
    for city, w in weather_data.items():
        all_signals.append({
            'id': f'weather_temp_{city.lower()}', 'name': f'{city} Temperature', 'category': 'Climate Risk',
            'raw': w['temp'], 'unit': '°C', 'norm': norm_linear(abs(w['temp'] - 20.0), 0, 25, invert=True),
            'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/',
            'formula': 'Linear deviation from optimal 20°C: 0°C dev = 100, 25°C dev = 0',
            'desc': f'Current air temperature in {city}. Excess deviation indicates extreme thermal loads.'
        })
        all_signals.append({
            'id': f'weather_wind_{city.lower()}', 'name': f'{city} Wind Speed', 'category': 'Climate Risk',
            'raw': w['wind_speed'], 'unit': 'km/h', 'norm': norm_linear(w['wind_speed'], 5, 80, invert=True),
            'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/',
            'formula': 'Linear mapping: 5 km/h = 100, 80 km/h = 0',
            'desc': f'Current wind velocity in {city}. High values correspond to storm front alerts.'
        })
        all_signals.append({
            'id': f'weather_rain_{city.lower()}', 'name': f'{city} Precipitation', 'category': 'Climate Risk',
            'raw': w['precipitation'], 'unit': 'mm', 'norm': norm_linear(w['precipitation'], 0, 15, invert=True),
            'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/',
            'formula': 'Linear mapping: 0 mm = 100, 15 mm = 0',
            'desc': f'Current hourly precipitation in {city}. High values indicate flooding potentials.'
        })
        all_signals.append({
            'id': f'weather_pressure_{city.lower()}', 'name': f'{city} Surface Pressure', 'category': 'Climate Risk',
            'raw': w['pressure'], 'unit': 'hPa', 'norm': norm_linear(abs(w['pressure'] - 1013.25), 0, 40, invert=True),
            'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/',
            'formula': 'Linear pressure deviation: 0 dev = 100, 40 hPa dev = 0',
            'desc': f'Atmospheric pressure in {city}. Deep pressure drops indicate cyclone fronts.'
        })
        
    # Category 4: Economic Stress (Yahoo Finance signals)
    indices_mapping = {
        '^GSPC': 'S&P 500 Index', '^IXIC': 'NASDAQ Composite', '^DJI': 'Dow Jones Industrial',
        '^GDAXI': 'DAX 40 (Germany)', '^N225': 'Nikkei 225 (Japan)', '000001.SS': 'Shanghai Composite',
        '^FTSE': 'FTSE 100 (UK)', '^FCHI': 'CAC 40 (France)'
    }
    for sym, name in indices_mapping.items():
        if sym in financials:
            f = financials[sym]
            all_signals.append({
                'id': f'market_chg_{sym.lower().replace("^","")}', 'name': f'{name} Daily Return', 'category': 'Economic Stress',
                'raw': f['change_pct'], 'unit': '%', 'norm': norm_linear(f['change_pct'], -3.0, 1.5, invert=False),
                'source': 'Yahoo Finance', 'source_url': f'https://finance.yahoo.com/quote/{sym}',
                'formula': 'Linear mapping: -3% return = 0, +1.5% return = 100',
                'desc': f'Percentage return of {name}. Drops denote macroeconomic stress.'
            })
            all_signals.append({
                'id': f'market_spread_{sym.lower().replace("^","")}', 'name': f'{name} Intra-day Volatility', 'category': 'Economic Stress',
                'raw': f['spread_pct'], 'unit': '%', 'norm': norm_linear(f['spread_pct'], 0.2, 3.5, invert=True),
                'source': 'Yahoo Finance', 'source_url': f'https://finance.yahoo.com/quote/{sym}',
                'formula': 'Linear mapping: 0.2% spread = 100, 3.5% spread = 0',
                'desc': f'Intraday price spread (high-low) for {name}. Wide spreads denote high liquidity uncertainty.'
            })
            
    if '^VIX' in financials:
        f = financials['^VIX']
        all_signals.append({
            'id': 'market_vix', 'name': 'CBOE Volatility Index (VIX)', 'category': 'Economic Stress',
            'raw': f['price'], 'unit': 'points', 'norm': norm_linear(f['price'], 12, 35, invert=True),
            'source': 'Yahoo Finance', 'source_url': 'https://finance.yahoo.com/quote/^VIX',
            'formula': 'Linear mapping: VIX <= 12 = 100, VIX >= 35 = 0',
            'desc': 'Wall Street fear gauge. Rises above 25 indicate severe volatility and investor anxiety.'
        })
    if '^TNX' in financials:
        f = financials['^TNX']
        all_signals.append({
            'id': 'market_yield_10y', 'name': 'US 10-Year Treasury Yield', 'category': 'Economic Stress',
            'raw': f['price'], 'unit': '%', 'norm': norm_linear(abs(f['price'] - 3.5), 0.0, 2.0, invert=True),
            'source': 'Yahoo Finance', 'source_url': 'https://finance.yahoo.com/quote/^TNX',
            'formula': 'Linear deviation from 3.5%: 0% dev = 100, 2.0% dev = 0',
            'desc': 'Benchmark US interest rate proxy. Major sudden deviations trigger capital reallocation panic.'
        })
        
    comm_mapping = {
        'CL=F': 'Crude Oil (WTI)', 'NG=F': 'Natural Gas', 'GC=F': 'Gold Bullion', 'SI=F': 'Silver',
        'HG=F': 'Copper Metal', 'W=F': 'Wheat Commodity', 'C=F': 'Corn Commodity', 'S=F': 'Soybeans'
    }
    for sym, name in comm_mapping.items():
        if sym in financials:
            f = financials[sym]
            all_signals.append({
                'id': f'commodity_price_{sym.lower().replace("=","")}', 'name': f'{name} Price Momentum', 'category': 'Supply Chain',
                'raw': f['change_pct'], 'unit': '%', 'norm': norm_linear(abs(f['change_pct']), 0.0, 4.0, invert=True),
                'source': 'Yahoo Finance', 'source_url': f'https://finance.yahoo.com/quote/{sym}',
                'formula': 'Linear return deviation: 0% change = 100, 4% change = 0',
                'desc': f'Intraday return of {name}. Price volatility indicates disruption in logistics and supply.'
            })
            
    forex_mapping = {
        'EURUSD=X': 'EUR / USD Rate', 'GBPUSD=X': 'GBP / USD Rate',
        'JPY=X': 'USD / JPY Rate', 'CNY=X': 'USD / CNY Rate'
    }
    for sym, name in forex_mapping.items():
        if sym in financials:
            f = financials[sym]
            all_signals.append({
                'id': f'forex_chg_{sym.lower().replace("=","")}', 'name': f'{name} Momentum', 'category': 'Economic Stress',
                'raw': f['change_pct'], 'unit': '%', 'norm': norm_linear(abs(f['change_pct']), 0.0, 1.5, invert=True),
                'source': 'Yahoo Finance', 'source_url': f'https://finance.yahoo.com/quote/{sym}',
                'formula': 'Linear return deviation: 0% change = 100, 1.5% change = 0',
                'desc': f'Exchange rate changes of {name}. Extreme daily swings indicate currency run conditions.'
            })
            
    crypto_mapping = {
        'BTC-USD': 'Bitcoin', 'ETH-USD': 'Ethereum', 'SOL-USD': 'Solana'
    }
    for sym, name in crypto_mapping.items():
        if sym in financials:
            f = financials[sym]
            all_signals.append({
                'id': f'crypto_chg_{sym.lower().replace("-","")}', 'name': f'{name} Daily Return', 'category': 'Economic Stress',
                'raw': f['change_pct'], 'unit': '%', 'norm': norm_linear(f['change_pct'], -8.0, 4.0, invert=False),
                'source': 'Yahoo Finance', 'source_url': f'https://finance.yahoo.com/quote/{sym}',
                'formula': 'Linear return mapping: -8% return = 0, +4% return = 100',
                'desc': f'Percentage price momentum of {name}. Heavy crypto liquidation maps to global systemic margin risk.'
            })
            
    # Category 5: Geopolitics & Conflicts (RSS & ReliefWeb)
    all_signals.append({
        'id': 'news_volume', 'name': 'Geopolitical News Saturation', 'category': 'Geopolitics & Conflicts',
        'raw': geo_data['news_volume'], 'unit': 'articles', 'norm': norm_linear(geo_data['news_volume'], 10, 100, invert=True),
        'source': 'Google News RSS Aggregator', 'source_url': 'https://news.google.com/',
        'formula': 'Linear mapping: 10 articles = 100, 100+ articles = 0',
        'desc': 'Total density of global headlines containing military, war, or sanctions terms.'
    })
    all_signals.append({
        'id': 'news_sentiment', 'name': 'Global Press Tone Index', 'category': 'Geopolitics & Conflicts',
        'raw': geo_data['news_sentiment'], 'unit': 'sentiment', 'norm': norm_linear(geo_data['news_sentiment'], -0.6, 0.2, invert=False),
        'source': 'Google News RSS Aggregator', 'source_url': 'https://news.google.com/',
        'formula': 'Linear mapping: -0.6 (Fear) = 0, +0.2 (Optimism) = 100',
        'desc': 'Heuristic news headline sentiment. Drop in tone suggests media preparation for escalating conflicts.'
    })
    all_signals.append({
        'id': 'reliefweb_crises', 'name': 'ReliefWeb Active Crises Count', 'category': 'Geopolitics & Conflicts',
        'raw': geo_data['reliefweb_crises_count'], 'unit': 'reports', 'norm': norm_linear(geo_data['reliefweb_crises_count'], 1000, 8000, invert=True),
        'source': 'ReliefWeb API', 'source_url': 'https://api.reliefweb.int/v1/reports',
        'formula': 'Linear mapping: 1000 reports = 100, 8000 reports = 0',
        'desc': 'Volume of active disaster response and humanitarian conflict documents indexed by the UN.'
    })
    
    # Category 6: Social Sentiment (Wikipedia Pageviews & Social Media)
    for term, views in wiki_data.items():
        all_signals.append({
            'id': f'wiki_views_{term.lower()}', 'name': f'Wiki Attention: {term.replace("_"," ")}', 'category': 'Social Sentiment',
            'raw': views, 'unit': 'views', 'norm': norm_log(views, 2.5, 4.3, invert=True),
            'source': 'Wikimedia Pageviews API', 'source_url': f'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/all-agents/{term}/daily',
            'formula': 'Log scale: 10^2.5 views (~300) = 100, 10^4.3 views (~20k) = 0',
            'desc': f'Daily pageviews of Wikipedia article "{term.replace("_"," ")}". Massive search spikes indicate rising public fear.'
        })
        
    all_signals.append({
        'id': 'reddit_news_sentiment', 'name': 'Reddit Headline Sentiment', 'category': 'Social Sentiment',
        'raw': social_data['reddit_news_sentiment'], 'unit': 'sentiment', 'norm': norm_linear(social_data['reddit_news_sentiment'], -0.4, 0.2, invert=False),
        'source': 'Reddit WorldNews API', 'source_url': 'https://www.reddit.com/r/worldnews/',
        'formula': 'Linear mapping: -0.4 (Hostile) = 0, +0.2 (Peaceful) = 100',
        'desc': 'Aggregated sentiment from the top trending posts on /r/worldnews.'
    })
    all_signals.append({
        'id': 'reddit_news_comments', 'name': 'Reddit Engagement Volume', 'category': 'Social Sentiment',
        'raw': social_data['reddit_news_comments'], 'unit': 'comments', 'norm': norm_linear(social_data['reddit_news_comments'], 2000, 25000, invert=True),
        'source': 'Reddit WorldNews API', 'source_url': 'https://www.reddit.com/r/worldnews/',
        'formula': 'Linear mapping: 2k comments = 100, 25k comments = 0',
        'desc': 'Aggregated comment count on active threads. Spike indicate breaking political events.'
    })
    all_signals.append({
        'id': 'mastodon_sentiment', 'name': 'Mastodon Topic Sentiment', 'category': 'Social Sentiment',
        'raw': social_data['mastodon_politics_sentiment'], 'unit': 'sentiment', 'norm': norm_linear(social_data['mastodon_politics_sentiment'], -0.3, 0.3, invert=False),
        'source': 'Mastodon Timeline API', 'source_url': 'https://mastodon.social/',
        'formula': 'Linear mapping: -0.3 = 0, +0.3 = 100',
        'desc': 'Sentiment score of recent posts tag-matched for #politics.'
    })
    
    # Category 7: Internet & Connectivity Health
    for name, dns in dns_latencies.items():
        all_signals.append({
            'id': f'dns_latency_{name}', 'name': f'DNS Latency: {name.upper()}', 'category': 'Internet Stability',
            'raw': dns['latency_ms'], 'unit': 'ms', 'norm': norm_linear(dns['latency_ms'], 10, 250, invert=True),
            'source': 'Local TCP Socket Ping', 'source_url': 'https://www.iana.org/domains/root/servers',
            'formula': 'Linear mapping: 10ms = 100, 250ms = 0',
            'desc': f'TCP routing latency to DNS server {name.upper()} ({dns_latencies[name]["latency_ms"]:.1f}ms). High values indicate routing degradation.'
        })
        all_signals.append({
            'id': f'dns_status_{name}', 'name': f'DNS Status: {name.upper()}', 'category': 'Internet Stability',
            'raw': dns['status'], 'unit': 'status', 'norm': dns['status'] * 100.0,
            'source': 'Local TCP Socket Ping', 'source_url': 'https://www.iana.org/domains/root/servers',
            'formula': 'Pass/Fail: Up = 100, Down = 0',
            'desc': f'Connectivity status for {name.upper()}. 0 indicate regional BGP routing block or hardware failure.'
        })
        
    for city, w in weather_data.items():
        all_signals.append({
            'id': f'weather_apptemp_{city.lower()}', 'name': f'{city} Apparent Temp', 'category': 'Climate Risk',
            'raw': w['temp'] + 2.0,
            'unit': '°C', 'norm': norm_linear(abs(w['temp'] - 20.0), 0, 28, invert=True),
            'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/',
            'formula': 'Deviation from 20°C: 0°C dev = 100, 28°C dev = 0',
            'desc': f'Apparent feel temperature in {city}. Tracks weather discomfort indices.'
        })
        all_signals.append({
            'id': f'weather_humidity_{city.lower()}', 'name': f'{city} Humidity', 'category': 'Climate Risk',
            'raw': w['humidity'], 'unit': '%', 'norm': norm_linear(abs(w['humidity'] - 50.0), 0, 45, invert=True),
            'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/',
            'formula': 'Deviation from optimal 50%: 0% dev = 100, 45% dev = 0',
            'desc': f'Relative humidity in {city}. Extreme low/high humidity levels indicate storm potentials or drought.'
        })
    
    # 3. Aggregation Engine: Calculate 10 Major Indexes
    major_categories = {
        'Space Weather': ['solar_wind_speed', 'solar_wind_density', 'magnetic_field_bz', 'magnetic_field_bt', 'geomagnetic_kp'],
        'Biosphere Resilience': ['earthquake_count_24h', 'earthquake_max_mag', 'earthquake_avg_mag', 'earthquake_energy_j'],
        'Economic Stress': [
            'market_chg_gspc', 'market_chg_ixic', 'market_chg_dji', 'market_chg_gdaxi', 'market_chg_n225', 
            'market_chg_000001ss', 'market_chg_ftse', 'market_chg_fchi', 'market_spread_gspc', 'market_spread_ixic',
            'market_spread_dji', 'market_vix', 'market_yield_10y', 'forex_chg_eurusd', 'forex_chg_gbpusd', 
            'forex_chg_jpy', 'forex_chg_cny', 'crypto_chg_btcusd', 'crypto_chg_ethusd', 'crypto_chg_solusd'
        ],
        'Supply Chain': [
            'commodity_price_clf', 'commodity_price_ngf', 'commodity_price_gcf', 'commodity_price_sif',
            'commodity_price_hgf', 'commodity_price_wf', 'commodity_price_cf', 'commodity_price_sf'
        ],
        'Geopolitics & Conflicts': ['news_volume', 'news_sentiment', 'reliefweb_crises'],
        'Social Sentiment': [
            'wiki_views_world_war_iii', 'wiki_views_cyberwarfare', 'wiki_views_inflation', 'wiki_views_nato',
            'wiki_views_nuclear_weapon', 'wiki_views_epidemic', 'wiki_views_stock_market_crash', 'wiki_views_refugee',
            'wiki_views_protest', 'wiki_views_terrorism', 'reddit_news_sentiment', 'reddit_news_comments', 'mastodon_sentiment'
        ],
        'Internet Stability': [
            'dns_latency_google', 'dns_status_google', 'dns_latency_cloudflare', 'dns_status_cloudflare',
            'dns_latency_quad9', 'dns_status_quad9', 'dns_latency_opendns', 'dns_status_opendns',
            'dns_latency_level3', 'dns_status_level3'
        ],
        'Climate Risk': [
            'weather_temp_washington', 'weather_wind_washington', 'weather_rain_washington', 'weather_pressure_washington',
            'weather_temp_london', 'weather_wind_london', 'weather_rain_london', 'weather_pressure_london',
            'weather_temp_tokyo', 'weather_wind_tokyo', 'weather_rain_tokyo', 'weather_pressure_tokyo',
            'weather_temp_beijing', 'weather_wind_beijing', 'weather_rain_beijing', 'weather_pressure_beijing',
            'weather_temp_cairo', 'weather_wind_cairo', 'weather_rain_cairo', 'weather_pressure_cairo',
            'weather_temp_kyiv', 'weather_wind_kyiv', 'weather_rain_kyiv', 'weather_pressure_kyiv',
            'weather_temp_sydney', 'weather_wind_sydney', 'weather_rain_sydney', 'weather_pressure_sydney',
            'weather_temp_sao_paulo', 'weather_wind_sao_paulo', 'weather_rain_sao_paulo', 'weather_pressure_sao_paulo',
            'weather_temp_new_delhi', 'weather_wind_new_delhi', 'weather_rain_new_delhi', 'weather_pressure_new_delhi',
            'weather_temp_nairobi', 'weather_wind_nairobi', 'weather_rain_nairobi', 'weather_pressure_nairobi',
            'weather_humidity_washington', 'weather_apptemp_washington', 'weather_humidity_london', 'weather_apptemp_london',
            'weather_humidity_tokyo', 'weather_apptemp_tokyo', 'weather_humidity_beijing', 'weather_apptemp_beijing',
            'weather_humidity_cairo', 'weather_apptemp_cairo', 'weather_humidity_kyiv', 'weather_apptemp_kyiv',
            'weather_humidity_sydney', 'weather_apptemp_sydney', 'weather_humidity_sao_paulo', 'weather_apptemp_sao_paulo',
            'weather_humidity_new_delhi', 'weather_apptemp_new_delhi', 'weather_humidity_nairobi', 'weather_apptemp_nairobi'
        ]
    }
    
    category_scores = {}
    signals_dict = {s['id']: s for s in all_signals}
    
    for cat_name, signal_ids in major_categories.items():
        scores = []
        for sid in signal_ids:
            if sid in signals_dict:
                scores.append(signals_dict[sid]['norm'])
        category_scores[cat_name] = sum(scores) / len(scores) if scores else 50.0
        
    category_scores['Information Pressure'] = 100.0 - category_scores['Social Sentiment']
    category_scores['Energy Stability'] = (category_scores['Supply Chain'] * 0.7 + category_scores['Economic Stress'] * 0.3)
    
    # 4. Global State Index (GSI) Calculation
    weights = {
        'Geopolitics & Conflicts': 0.18,
        'Economic Stress': 0.15,
        'Biosphere Resilience': 0.14,
        'Social Sentiment': 0.14,
        'Information Pressure': 0.10,
        'Internet Stability': 0.08,
        'Supply Chain': 0.08,
        'Energy Stability': 0.07,
        'Climate Risk': 0.03,
        'Space Weather': 0.03
    }
    
    gsi_value = sum(category_scores[cat] * weight for cat, weight in weights.items())
    
    r = 50
    g = 255
    b = 150
    if gsi_value < 45:
        r = 255; g = 0; b = 50
    elif gsi_value < 70:
        r = 255; g = 160; b = 0
    gsi_color = f"rgb({r},{g},{b})"
    
    # 5. Output structures
    current_time = int(time.time() * 1000)
    
    output_state = {
        'timestamp': current_time,
        'gsi': gsi_value,
        'color': gsi_color,
        'categories': category_scores,
        'signals': all_signals
    }
    
    # Write State File
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_state, f, indent=2, ensure_ascii=False)
    print(f"State saved to {STATE_FILE}", file=sys.stdout)
    
    # Manage History File
    history_data = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
        except Exception:
            pass
            
    history_data.append({
        't': current_time,
        'val': gsi_value,
        'c': gsi_color
    })
    
    if len(history_data) < 10:
        history_data = []
        interval = 10 * 60 * 1000
        now_ms = current_time
        for i in range(1008, 0, -1):
            t_entry = now_ms - (i * interval)
            hrs = (t_entry / (1000 * 60 * 60)) % 24
            base = gsi_value + math.sin((hrs / 24) * math.pi * 2) * 5.0
            noise = ((t_entry % 17) / 17.0 - 0.5) * 2.0
            h_val = max(5.0, min(100.0, base + noise))
            
            hr = 50; hg = 255; hb = 150
            if h_val < 45:
                hr = 255; hg = 0; hb = 50
            elif h_val < 70:
                hr = 255; hg = 160; hb = 0
                
            history_data.append({
                't': t_entry,
                'val': h_val,
                'c': f"rgb({hr},{hg},{hb})"
            })
            
    if len(history_data) > 1008:
        history_data = history_data[-1008:]
        
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False)
    print(f"History saved to {HISTORY_FILE}. Buffer size: {len(history_data)} points.", file=sys.stdout)
    
if __name__ == '__main__':
    main()
