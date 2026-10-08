"""
Word lookup: proxies to the Sefaria Lexicon API (GET https://www.sefaria.org/api/words/{word}).

fetch_words() returns (status, JSON body bytes), ready to send to the browser.
"""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request

SEFARIA_BASE = "https://www.sefaria.org/api/words/"
ALLOWED_PARAMS = ("lookup_ref", "never_split", "always_split", "always_consonants")
TIMEOUT = 20
CACHE = {}          # simple in-memory cache: url -> (status, body)
CACHE_MAX = 500
CACHE_LOCK = threading.Lock()  # requests are served on multiple threads


def fetch_words(word, params):
    query = {k: v for k, v in params.items() if k in ALLOWED_PARAMS and v != ""}
    url = SEFARIA_BASE + urllib.parse.quote(word, safe="")
    if query:
        url += "?" + urllib.parse.urlencode(query)
    with CACHE_LOCK:
        cached = CACHE.get(url)
    if cached:
        return cached
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "benneria/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        body = json.dumps({"error": f"Sefaria returned HTTP {e.code}"}).encode()
        status = 502
    except Exception as e:  # network errors, timeouts
        body = json.dumps({"error": f"Could not reach Sefaria: {e}"}).encode()
        status = 502
    if status == 200:
        with CACHE_LOCK:
            if url not in CACHE and len(CACHE) >= CACHE_MAX:
                CACHE.pop(next(iter(CACHE)))
            CACHE[url] = (status, body)
    return status, body
