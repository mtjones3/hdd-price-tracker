#!/usr/bin/env python3
"""
HDD Price Scraper — Seagate vs WD
Scrapes current prices from Newegg and Amazon, appends daily snapshots to
prices.json, then commits + pushes so Netlify auto-deploys the updated tracker.

Usage:
  python scraper.py            # scrape + push
  python scraper.py --no-push  # scrape only (for testing)
  python scraper.py --test 3   # test first 3 products only
"""

import json, time, random, subprocess, re, sys, argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).parent
PRICES_FILE = REPO / "prices.json"
TODAY = str(date.today())

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
})


# ── PRODUCT CONFIG ─────────────────────────────────────────────────────────────
# sources: list of {name, url} tried in order; first success wins.
# Newegg model-number search (/p/pl?d=MODEL) usually hits product page.
# Amazon ASINs need luck with bot detection; they're fallbacks.

PRODUCTS_CONFIG = [
    # ── SEAGATE NAS ──────────────────────────────────────────────────────────
    {"id":"sgt-iw-2tb",    "brand":"Seagate","series":"IronWolf",     "seg":"nas",         "cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST2000VN003"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B09MXLDNFC"}]},
    {"id":"sgt-iw-4tb",    "brand":"Seagate","series":"IronWolf",     "seg":"nas",         "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST4000VN006"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07H289S7C"}]},
    {"id":"sgt-iw-6tb",    "brand":"Seagate","series":"IronWolf",     "seg":"nas",         "cap":"6TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST6000VN001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07H3SPB3D"}]},
    {"id":"sgt-iw-8tb",    "brand":"Seagate","series":"IronWolf",     "seg":"nas",         "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST8000VN004"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B084ZTSSTP"}]},
    {"id":"sgt-iw-10tb",   "brand":"Seagate","series":"IronWolf",     "seg":"nas",         "cap":"10TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST10000VN0008"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07H3TX2YR"}]},
    {"id":"sgt-iw-12tb",   "brand":"Seagate","series":"IronWolf",     "seg":"nas",         "cap":"12TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST12000VN0008"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B08D93Y7NK"}]},
    {"id":"sgt-iw-16tb",   "brand":"Seagate","series":"IronWolf",     "seg":"nas",         "cap":"16TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST16000VN001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B08XGW2JVM"}]},
    {"id":"sgt-iwp-2tb",   "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST2000NT001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07FFJSH9N"}]},
    {"id":"sgt-iwp-4tb",   "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST4000NT001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07H3TX2NJ"}]},
    {"id":"sgt-iwp-8tb",   "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST8000NT001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B01GVV7PVQ"}]},
    {"id":"sgt-iwp-12tb",  "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"12TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST12000NT001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07H3TX28Q"}]},
    {"id":"sgt-iwp-16tb",  "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"16TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST16000NT001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B08XH5DZMP"}]},
    {"id":"sgt-iwp-20tb",  "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"20TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST20000NT001"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B09Y3DQMXZ"}]},
    {"id":"sgt-iwp-24tb",  "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"24TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST24000NT002"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B0B35BQBNL"}]},
    {"id":"sgt-iwp-28tb",  "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"28TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST28000NT001"}]},
    {"id":"sgt-iwp-32tb",  "brand":"Seagate","series":"IronWolf Pro", "seg":"nas",         "cap":"32TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST32000NT000"}]},

    # ── SEAGATE DESKTOP ──────────────────────────────────────────────────────
    {"id":"sgt-bc-1tb",    "brand":"Seagate","series":"BarraCuda",    "seg":"desktop",     "cap":"1TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST1000DM010"}]},
    {"id":"sgt-bc-2tb",    "brand":"Seagate","series":"BarraCuda",    "seg":"desktop",     "cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST2000DM008"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B01LNJBA2I"}]},
    {"id":"sgt-bc-4tb",    "brand":"Seagate","series":"BarraCuda",    "seg":"desktop",     "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST4000DM004"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07H2RR55Q"}]},
    {"id":"sgt-bc-8tb",    "brand":"Seagate","series":"BarraCuda",    "seg":"desktop",     "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST8000DM004"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07MY2C19F"}]},
    {"id":"sgt-bc-12tb",   "brand":"Seagate","series":"BarraCuda",    "seg":"desktop",     "cap":"12TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST12000DM0007"}]},

    # ── SEAGATE SURVEILLANCE ─────────────────────────────────────────────────
    {"id":"sgt-sh-2tb",    "brand":"Seagate","series":"SkyHawk",      "seg":"surveillance","cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST2000VX015"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07DF88CS3"}]},
    {"id":"sgt-sh-4tb",    "brand":"Seagate","series":"SkyHawk",      "seg":"surveillance","cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST4000VX016"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B07B98C8TT"}]},
    {"id":"sgt-sh-8tb",    "brand":"Seagate","series":"SkyHawk",      "seg":"surveillance","cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST8000VX010"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B01IAD6B4G"}]},

    # ── SEAGATE ENTERPRISE ───────────────────────────────────────────────────
    {"id":"sgt-ex16-16tb", "brand":"Seagate","series":"Exos X16",     "seg":"enterprise",  "cap":"16TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST16000NM002G"}]},
    {"id":"sgt-ex18-18tb", "brand":"Seagate","series":"Exos X18",     "seg":"enterprise",  "cap":"18TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST18000NM000J"},
                {"name":"amazon","url":"https://www.amazon.com/dp/B08CQHSP6Z"}]},
    {"id":"sgt-ex20-20tb", "brand":"Seagate","series":"Exos X20",     "seg":"enterprise",  "cap":"20TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST20000NM007D"}]},
    {"id":"sgt-bc520-20tb","brand":"Seagate","series":"BarraCuda 520","seg":"enterprise",  "cap":"20TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=ST20000DM001"}]},

    # ── WD DESKTOP ───────────────────────────────────────────────────────────
    {"id":"wd-blue-500gb", "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"500GB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD5000AAKX"}]},
    {"id":"wd-blue-1tb",   "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"1TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD10EZEX"}]},
    {"id":"wd-blue-2tb",   "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD20EARZ"}]},
    {"id":"wd-blue-4tb",   "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD40EZAX"}]},
    {"id":"wd-blue-6tb",   "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"6TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD60EZAX"}]},
    {"id":"wd-blue-8tb",   "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD80EAZZ"}]},
    {"id":"wd-blue-10tb",  "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"10TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD100EAGZ"}]},
    {"id":"wd-blue-12tb",  "brand":"WD",     "series":"Blue",         "seg":"desktop",     "cap":"12TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD120EAGZ"}]},
    {"id":"wd-green-4tb",  "brand":"WD",     "series":"Green",        "seg":"desktop",     "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD40EZRX"}]},

    # ── WD NAS ───────────────────────────────────────────────────────────────
    {"id":"wd-rp-2tb",     "brand":"WD",     "series":"Red Plus",     "seg":"nas",         "cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD20EFRX"}]},
    {"id":"wd-rp-3tb",     "brand":"WD",     "series":"Red Plus",     "seg":"nas",         "cap":"3TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD30EFRX"}]},
    {"id":"wd-rp-4tb",     "brand":"WD",     "series":"Red Plus",     "seg":"nas",         "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD40EFRX"}]},
    {"id":"wd-rp-6tb",     "brand":"WD",     "series":"Red Plus",     "seg":"nas",         "cap":"6TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD60EFPX"}]},
    {"id":"wd-rp-8tb",     "brand":"WD",     "series":"Red Plus",     "seg":"nas",         "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD80EFPX"}]},
    {"id":"wd-rp-10tb",    "brand":"WD",     "series":"Red Plus",     "seg":"nas",         "cap":"10TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD101EFBX"}]},
    {"id":"wd-rp-12tb",    "brand":"WD",     "series":"Red Plus",     "seg":"nas",         "cap":"12TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD120EFGX"}]},
    {"id":"wd-rpro-4tb",   "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD4001FFSX"}]},
    {"id":"wd-rpro-6tb",   "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"6TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD6005FFBX"}]},
    {"id":"wd-rpro-8tb",   "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD8005FFBX"}]},
    {"id":"wd-rpro-10tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"10TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD103KFBX"}]},
    {"id":"wd-rpro-12tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"12TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD122KFBX"}]},
    {"id":"wd-rpro-14tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"14TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD142KFGX"}]},
    {"id":"wd-rpro-16tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"16TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD161KFGX"}]},
    {"id":"wd-rpro-18tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"18TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD181KFGX"}]},
    {"id":"wd-rpro-22tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"22TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD221KFGX"}]},
    {"id":"wd-rpro-24tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"24TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD241KFGX"}]},
    {"id":"wd-rpro-26tb",  "brand":"WD",     "series":"Red Pro",      "seg":"nas",         "cap":"26TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD260KFGX"}]},

    # ── WD SURVEILLANCE ──────────────────────────────────────────────────────
    {"id":"wd-pur-2tb",    "brand":"WD",     "series":"Purple",       "seg":"surveillance","cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD23PURZ"}]},
    {"id":"wd-pur-6tb",    "brand":"WD",     "series":"Purple",       "seg":"surveillance","cap":"6TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD64PURZ"}]},
    {"id":"wd-pur-8tb",    "brand":"WD",     "series":"Purple",       "seg":"surveillance","cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD85PURZ"}]},
    {"id":"wd-purp-8tb",   "brand":"WD",     "series":"Purple Pro",   "seg":"surveillance","cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD8001PURP"}]},
    {"id":"wd-purp-10tb",  "brand":"WD",     "series":"Purple Pro",   "seg":"surveillance","cap":"10TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD102PURP"}]},

    # ── WD ENTERPRISE ────────────────────────────────────────────────────────
    {"id":"wd-gold-6tb",   "brand":"WD",     "series":"Gold",         "seg":"enterprise",  "cap":"6TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD6004FRYZ"}]},
    {"id":"wd-gold-8tb",   "brand":"WD",     "series":"Gold",         "seg":"enterprise",  "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD8005FRYZ"}]},
    {"id":"wd-gold-12tb",  "brand":"WD",     "series":"Gold",         "seg":"enterprise",  "cap":"12TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD122KRYZ"}]},
    {"id":"wd-gold-18tb",  "brand":"WD",     "series":"Gold",         "seg":"enterprise",  "cap":"18TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD181KRYZ"}]},
    {"id":"wd-gold-20tb",  "brand":"WD",     "series":"Gold",         "seg":"enterprise",  "cap":"20TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD203KRYZ"}]},
    {"id":"wd-gold-24tb",  "brand":"WD",     "series":"Gold",         "seg":"enterprise",  "cap":"24TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD241KRYZ"}]},
    {"id":"wd-ult-14tb",   "brand":"WD",     "series":"Ultrastar",    "seg":"enterprise",  "cap":"14TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=0F31284"}]},

    # ── WD GAMING ────────────────────────────────────────────────────────────
    {"id":"wd-blk-2tb",    "brand":"WD",     "series":"Black",        "seg":"gaming",      "cap":"2TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD2003FZEX"}]},
    {"id":"wd-blk-4tb",    "brand":"WD",     "series":"Black",        "seg":"gaming",      "cap":"4TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD4006FZBX"}]},
    {"id":"wd-blk-6tb",    "brand":"WD",     "series":"Black",        "seg":"gaming",      "cap":"6TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD6004FZBX"}]},
    {"id":"wd-blk-8tb",    "brand":"WD",     "series":"Black",        "seg":"gaming",      "cap":"8TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD8002FZBX"}]},
    {"id":"wd-blk-10tb",   "brand":"WD",     "series":"Black",        "seg":"gaming",      "cap":"10TB",
     "sources":[{"name":"newegg","url":"https://www.newegg.com/p/pl?d=WD102FZBX"}]},
]


# ── SEED PRICES (initial baseline, Mar 11 2026) ───────────────────────────────
SEED_PRICES = {
    "sgt-iw-2tb":130,"sgt-iw-4tb":135,"sgt-iw-6tb":115,"sgt-iw-8tb":175,
    "sgt-iw-10tb":195,"sgt-iw-12tb":299,"sgt-iw-16tb":525,
    "sgt-iwp-2tb":100,"sgt-iwp-4tb":135,"sgt-iwp-8tb":235,"sgt-iwp-12tb":375,
    "sgt-iwp-16tb":490,"sgt-iwp-20tb":440,"sgt-iwp-24tb":599,"sgt-iwp-28tb":699,"sgt-iwp-32tb":760,
    "sgt-bc-1tb":67,"sgt-bc-2tb":89,"sgt-bc-4tb":112,"sgt-bc-8tb":175,"sgt-bc-12tb":230,
    "sgt-sh-2tb":70,"sgt-sh-4tb":89,"sgt-sh-8tb":149,
    "sgt-ex16-16tb":370,"sgt-ex18-18tb":345,"sgt-ex20-20tb":376,"sgt-bc520-20tb":516,
    "wd-blue-500gb":29.99,"wd-blue-1tb":59,"wd-blue-2tb":85.42,"wd-blue-4tb":104.99,
    "wd-blue-6tb":159.99,"wd-blue-8tb":204.99,"wd-blue-10tb":239.99,"wd-blue-12tb":269.99,
    "wd-green-4tb":114.95,
    "wd-rp-2tb":90,"wd-rp-3tb":170,"wd-rp-4tb":112,"wd-rp-6tb":321.45,
    "wd-rp-8tb":180,"wd-rp-10tb":274.99,"wd-rp-12tb":280,
    "wd-rpro-4tb":219,"wd-rpro-6tb":374.45,"wd-rpro-8tb":454.45,"wd-rpro-10tb":274.99,
    "wd-rpro-12tb":292.79,"wd-rpro-14tb":489.95,"wd-rpro-16tb":599.95,"wd-rpro-18tb":555,
    "wd-rpro-22tb":740,"wd-rpro-24tb":599.99,"wd-rpro-26tb":687.90,
    "wd-pur-2tb":119.99,"wd-pur-6tb":196.99,"wd-pur-8tb":261.99,
    "wd-purp-8tb":302.99,"wd-purp-10tb":314.99,
    "wd-gold-6tb":310.01,"wd-gold-8tb":424.45,"wd-gold-12tb":544.45,
    "wd-gold-18tb":375.99,"wd-gold-20tb":646.75,"wd-gold-24tb":710,
    "wd-ult-14tb":329.99,
    "wd-blk-2tb":129.99,"wd-blk-4tb":185.75,"wd-blk-6tb":204.99,
    "wd-blk-8tb":301.74,"wd-blk-10tb":342.98,
}
SEED_DATE = "2026-03-11"


# ── SCRAPING HELPERS ──────────────────────────────────────────────────────────
def _price_from_jsonld(soup):
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') != 'Product':
                    continue
                offers = item.get('offers', {})
                if isinstance(offers, list):
                    valid = [o for o in offers if o.get('price')]
                    if not valid:
                        continue
                    offers = min(valid, key=lambda x: float(str(x['price']).replace(',', '')))
                price = offers.get('price') or offers.get('lowPrice')
                avail = str(offers.get('availability', ''))
                if price:
                    p = float(str(price).replace(',', ''))
                    stock = 'InStock' in avail or 'LimitedAvailability' in avail
                    return p, stock
        except Exception:
            pass
    return None, None


def _price_from_meta(soup):
    pt = soup.find('meta', property='product:price:amount')
    at = soup.find('meta', property='product:availability')
    if pt:
        try:
            p = float(pt.get('content', '').replace(',', ''))
            stock = 'instock' in (at.get('content', '') if at else '').lower()
            return p, stock
        except Exception:
            pass
    return None, None


def _price_from_newegg_state(soup):
    """Try extracting from Newegg's __INITIAL_STATE__ JSON bundle."""
    for script in soup.find_all('script'):
        text = script.string or ''
        if 'window.__INITIAL_STATE__' not in text:
            continue
        try:
            m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+\})\s*;?\s*(?:window\.|$)', text, re.DOTALL)
            if not m:
                continue
            state = json.loads(m.group(1))
            items = (state.get('productlist', {}).get('productList', {}).get('items') or
                     state.get('product', {}).get('item', {}).get('selling', {}).get('prices') or [])
            if items:
                prices = [float(i.get('unitPrice', 0)) for i in items if i.get('unitPrice')]
                if prices:
                    return min(prices), True
        except Exception:
            pass
    return None, None


def scrape_url(url, src_name):
    """Scrape a single URL. Returns (price, in_stock) or (None, None)."""
    try:
        delay = random.uniform(2.0, 4.5)
        time.sleep(delay)
        r = SESSION.get(url, timeout=25, allow_redirects=True)
        if r.status_code != 200:
            print(f"    HTTP {r.status_code}")
            return None, None
        soup = BeautifulSoup(r.content, 'lxml')

        # Try extraction methods in order
        for fn in (_price_from_jsonld, _price_from_meta, _price_from_newegg_state):
            price, stock = fn(soup)
            if price and price > 0:
                return round(price, 2), stock

        return None, None
    except Exception as e:
        print(f"    Error: {e}")
        return None, None


# ── DATA STORE ────────────────────────────────────────────────────────────────
def load_prices():
    if PRICES_FILE.exists():
        return json.loads(PRICES_FILE.read_text(encoding='utf-8'))

    # First run — seed from hardcoded baseline
    print("⚙  First run — seeding prices.json from baseline...")
    products = []
    for p in PRODUCTS_CONFIG:
        seed = SEED_PRICES.get(p['id'])
        history = [{"date": SEED_DATE, "price": seed, "stock": True, "src": "manual"}] if seed else []
        products.append({**{k: p[k] for k in ('id','brand','series','seg','cap')}, "history": history})
    return {"version": 1, "lastScraped": SEED_DATE, "products": products}


def save_prices(data):
    PRICES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def get_product_record(data, pid):
    for p in data['products']:
        if p['id'] == pid:
            return p
    return None


def update_history(record, price, stock, src):
    """Append today's price; replace if we already scraped today."""
    hist = record.setdefault('history', [])
    if hist and hist[-1]['date'] == TODAY:
        hist[-1].update(price=price, stock=stock, src=src)
    else:
        hist.append({"date": TODAY, "price": price, "stock": stock, "src": src})
    # Keep max 365 entries
    record['history'] = hist[-365:]


# ── MAIN SCRAPE LOOP ──────────────────────────────────────────────────────────
def run(args):
    data = load_prices()

    # Ensure all config products exist in data
    existing_ids = {p['id'] for p in data['products']}
    for cfg in PRODUCTS_CONFIG:
        if cfg['id'] not in existing_ids:
            seed = SEED_PRICES.get(cfg['id'])
            hist = [{"date": SEED_DATE, "price": seed, "stock": True, "src": "manual"}] if seed else []
            data['products'].append({**{k: cfg[k] for k in ('id','brand','series','seg','cap')}, "history": hist})

    configs_to_scrape = PRODUCTS_CONFIG[:args.test] if args.test else PRODUCTS_CONFIG
    total = len(configs_to_scrape)
    success, skipped = 0, 0

    print(f"\n{'='*60}")
    print(f"  HDD Price Scraper — {TODAY}")
    print(f"  Products to scrape: {total}")
    print(f"{'='*60}\n")

    for i, cfg in enumerate(configs_to_scrape, 1):
        rec = get_product_record(data, cfg['id'])
        if not rec:
            continue

        # Skip if already scraped today (unless --force)
        if not args.force and rec.get('history') and rec['history'][-1]['date'] == TODAY:
            print(f"[{i}/{total}] ⏭  {cfg['brand']} {cfg['series']} {cfg['cap']} — already scraped today")
            skipped += 1
            continue

        print(f"[{i}/{total}] 🔍 {cfg['brand']} {cfg['series']} {cfg['cap']}...", end=' ', flush=True)
        found = False
        for src in cfg['sources']:
            price, stock = scrape_url(src['url'], src['name'])
            if price:
                update_history(rec, price, stock, src['name'])
                trend = ''
                if len(rec['history']) >= 2:
                    prev = rec['history'][-2]['price']
                    diff = price - prev
                    if abs(diff) > 0.01:
                        trend = f"  ({'+' if diff>0 else ''}{diff:.2f} vs prev)"
                print(f"✓ ${price:.2f} {'✔' if stock else '✗'} [{src['name']}]{trend}")
                found = True
                success += 1
                break
        if not found:
            print("✗ no price found (keeping last known)")

    data['lastScraped'] = TODAY
    save_prices(data)
    print(f"\n✅ Done — {success} updated, {skipped} skipped, {total-success-skipped} failed")
    print(f"   Saved to {PRICES_FILE}\n")

    if not args.no_push:
        git_push()


def git_push():
    print("📤 Committing + pushing to GitHub...")
    cmds = [
        ["git", "add", "prices.json"],
        ["git", "commit", "-m", f"Price update {TODAY}"],
        ["git", "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        if result.returncode != 0 and 'nothing to commit' not in result.stdout:
            print(f"   ⚠ {' '.join(cmd)}: {result.stderr.strip()}")
        else:
            print(f"   ✓ {' '.join(cmd)}")
    print("   🚀 Netlify deploy triggered via GitHub webhook\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='HDD Price Scraper')
    parser.add_argument('--no-push', action='store_true', help='Skip git push')
    parser.add_argument('--force',   action='store_true', help='Re-scrape even if already done today')
    parser.add_argument('--test',    type=int, metavar='N', help='Only scrape first N products')
    args = parser.parse_args()
    run(args)
