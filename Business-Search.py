"""
Summary
    1. Have your own Serper API key
    2. Multi-country iterative search for consistent global results
    3. Maintains strict quality filters (no compromises)
    4. Searches major countries until finding high-quality businesses
Filter:
    1. Website only
    2. Any social media platform that is not specific only to the business
    3. Rating above 4 star only (NEVER lowered)
    4. 50+ reviews (NEVER lowered)
    5. Actual business only that can be found in Maps
Strategy:
    Search multiple countries iteratively:
    - Start with major markets (US, UK, etc.)
    - Stop when enough results found
    - Deduplicates across countries
    - Guarantees consistent results
"""
import json
import re
import csv
import sys
from typing  import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from PySide6.QtCore    import QThread, Signal
from PySide6.QtGui     import QFont, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox,
    QPlainTextEdit, QFileDialog, QGroupBox,
)

# Add or Delete base on preferred countries
SEARCH_COUNTRIES = [
    "United States",
    "United Kingdom", 
    "Canada",
    "Australia",
    "Germany",
    "France",
    "Singapore",
    "Japan",
    "Netherlands",
    "Sweden",
    "Switzerland",
    "Ireland",
    "New Zealand",
    "United Arab Emirates",
    "South Korea",
]

# Add or Delete base on your preference for sources
BLACKLISTED_DOMAINS = {
    "reddit.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com", "tiktok.com", "linkedin.com",
    "pinterest.com", "yelp.com", "tripadvisor.com", "quora.com",
    "wikipedia.org", "buzzfeed.com", "tumblr.com", "snapchat.com",
    "threads.net", "whatsapp.com", "telegram.org", "twitch.tv",
    "amazon.com", "ebay.com", "aliexpress.com",
    "google.com", "bing.com",
}

# Add or Delete base on road network format
_STREET_SUFFIXES = (
    r"Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|"
    r"Lane|Ln|Way|Pl|Quay|Place|Court|Ct|Terrace|Tce|Crescent|Cres"
)
_FULL_ADDR_RE = re.compile(
    r"(\d+\s+[\w\s]+?"
    r"(?:" + _STREET_SUFFIXES + r")"
    r"[\w\s,.\-]*)",
    re.IGNORECASE,
)


def is_blacklisted(url: str) -> bool:
    """Filter by domain AND URL path patterns."""
    domain = urlparse(url).netloc.lower().lstrip("www.")

    if any(bl in domain for bl in BLACKLISTED_DOMAINS):
        return True
    
    path = urlparse(url).path.lower()
    bad_paths = [
        "/blog/", "/article/", "/news/", "/press/",
        "/directory/", "/list/", "/ranking/", "/top-",
        "/statistics/", "/guide/", "/resources/",
        "/insights/", "/report/", "/research/",
    ]
    return any(bp in path for bp in bad_paths)


def scrape_location(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BusinessResearchBot/1.0)"
        })
        resp.raise_for_status()
    except requests.RequestException:
        return None
    return _parse_location_from_html(resp.text)


def _parse_location_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data  = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                addr = item.get("address", {})
                if isinstance(addr, str) and addr.strip():
                    return addr.strip()
                if isinstance(addr, dict):
                    parts = [
                        addr.get("streetAddress", ""),
                        addr.get("addressLocality", ""),
                        addr.get("addressRegion", ""),
                        addr.get("postalCode", ""),
                        addr.get("addressCountry", ""),
                    ]
                    joined = ", ".join(p for p in parts if p).strip()
                    if joined:
                        return joined
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    addr_tag = soup.find("address")
    if addr_tag and addr_tag.get_text(strip=True):
        return addr_tag.get_text(strip=True)

    for tag in soup.find_all(["p", "span", "div", "li", "footer", "section"]):
        text = tag.get_text(strip=True)
        if len(text) > 250:
            continue
        m = _FULL_ADDR_RE.search(text)
        if m:
            return m.group(1).strip().rstrip(",. ")

    return None


def serper_search(api_key: str, query: str, num: int = 10, location: str = None) -> Dict:
    """Search with optional location parameter."""
    payload = {"q": query, "num": num}
    if location:
        payload["location"] = location
    
    resp = requests.post(
        "https://google.serper.dev/places", 
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def clean_name(title: str) -> str:
    name = re.sub(r"\s*[-\u2013|]\s*.*$", "", title)
    name = re.sub(r"\s*[(\[].*?[)\]]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    for word in ("Reviews", "Official Site", "Home", "Website", "Official"):
        if name.endswith(word):
            name = name[: -len(word)].strip()
    return name


def maps_link(name: str, location: Optional[str] = None) -> str:
    query = f"{name} {location}" if location else name
    return f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}"

class ResearchWorker(QThread):
    log      = Signal(str)       
    finished = Signal(list, int)
    error    = Signal(str)      

    def __init__(self, api_key: str, idea: str, num: int):
        super().__init__()
        self.api_key = api_key
        self.idea    = idea
        self.num     = num
        
        # FILTERS
        self.MIN_RATING = 4.0
        self.MIN_REVIEWS = 50
        
        # COUNTER
        self.api_calls_made = 0

    def run(self):            
        try:
            businesses = self._multi_country_search()
            
            if not businesses:
                self.error.emit(
                    f"No high-quality businesses found across {len(SEARCH_COUNTRIES)} countries.\n"
                    f"Searched: {', '.join(SEARCH_COUNTRIES[:5])}...\n"
                    f"Try: More specific terms like '{self.idea} franchise' or brand names"
                )
                return

            self.finished.emit(businesses, self.api_calls_made)

        except requests.exceptions.HTTPError as e:
            self.error.emit(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            self.error.emit(str(e))
    
    def _multi_country_search(self) -> List[Dict]:
        """Search multiple countries iteratively until enough results found."""
        
        all_places = []
        seen_cids = set()
        countries_searched = 0
        
        self.log.emit(f"🌍 Starting multi-country search for '{self.idea}'...")
        self.log.emit(f"🎯 Target: {self.num} businesses (4.0★+, 50+ reviews, website)\n")
        
        # Iteration for search
        for country in SEARCH_COUNTRIES:
            countries_searched += 1
            
            self.log.emit(f"🔍 Searching in {country}...")
            
            # Fetch from this country
            places = self._fetch_and_dedupe(self.idea, num=20, location=country, seen_cids=seen_cids)
            all_places.extend(places)
            
            self.log.emit(f"   → Found {len(places)} new unique places")

            filtered = self._apply_strict_filters(all_places, log_stats=False)

            if len(filtered) >= self.num * 2:  # change no for buffer
                self.log.emit(f"\n✅ Sufficient results found after searching {countries_searched} countries")
                break
            
            # rate limiting
            import time
            time.sleep(0.3)
        
        self.log.emit(f"\n📊 Total places collected: {len(all_places)} (from {countries_searched} countries)")
        self.log.emit(f"📞 API calls made: {self.api_calls_made}")
        self.log.emit("🎯 Applying strict filters...\n")
        
        return self._apply_strict_filters(all_places, log_stats=True)
    
    def _fetch_and_dedupe(self, query: str, num: int, location: str, seen_cids: set) -> List[Dict]:
        """Fetch places from a specific location and deduplicate by CID."""
        try:
            raw = serper_search(self.api_key, query, num=num, location=location)
            self.api_calls_made += 1  # Increment counter
            places = raw.get("places", [])

            new_places = []
            for place in places:
                cid = place.get("cid", "")
                if cid and cid not in seen_cids:
                    seen_cids.add(cid)
                    new_places.append(place)
            
            return new_places
        except Exception as e:
            self.log.emit(f"   ⚠️  Error: {str(e)[:50]}")
            return []
    
    def _apply_strict_filters(self, places: list, log_stats: bool = True) -> List[Dict]:
        """Apply STRICT filters - NEVER compromised."""
        filtered = []
        
        stats = {
            "no_website": 0,
            "blacklisted": 0,
            "low_rating": 0,
            "low_reviews": 0,
            "passed": 0
        }
        
        # FILTER
        for place in places:
            # Website required
            website = place.get("website", "")
            if not website:
                stats["no_website"] += 1
                continue
            
            # Blacklist check
            if is_blacklisted(website):
                stats["blacklisted"] += 1
                continue
            
            # Rating >= 4.0
            rating = place.get("rating", 0)
            if rating is None:
                rating = 0
            if rating < self.MIN_RATING:
                stats["low_rating"] += 1
                continue
            
            # Reviews >= 50
            review_count = place.get("ratingCount", 0)
            if review_count is None:
                review_count = 0
            if review_count < self.MIN_REVIEWS:
                stats["low_reviews"] += 1
                continue
            
            stats["passed"] += 1
            filtered.append(place)
        
        # Log filter statistics
        if log_stats:
            total = len(places)
            self.log.emit("Filter results:")
            self.log.emit(f"  • Total places: {total}")
            self.log.emit(f"  • No website: {stats['no_website']}")
            self.log.emit(f"  • Blacklisted: {stats['blacklisted']}")
            self.log.emit(f"  • Rating < 4.0★: {stats['low_rating']}")
            self.log.emit(f"  • Reviews < 50: {stats['low_reviews']}")
            self.log.emit(f"  ✅ Passed all filters: {stats['passed']}\n")

        businesses: List[Dict] = []
        for idx, place in enumerate(filtered[:self.num], 1):
            name     = place.get("title", "")
            address  = place.get("address", "Location not specified")
            rating   = place.get("rating", 0)
            reviews  = place.get("ratingCount", 0)
            website  = place.get("website", "")  
            cid      = place.get("cid", "")

            if rating is None:
                rating = 0
            if reviews is None:
                reviews = 0
            
            if cid:
                maps_url = f"https://www.google.com/maps/?cid={cid}"
            else:
                maps_url = maps_link(name, address)

            businesses.append({
                "rank":             idx,
                "name":             name,
                "website":          website,
                "description":      f"{rating}★ ({reviews:,} reviews)",
                "location":         address,
                "rating":           rating,
                "review_count":     reviews,
                "google_maps_link": maps_url,
                "extracted_at":     datetime.now().isoformat(),
            })
        
        return businesses

# ═════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Business Competitor Researcher - Global Multi-Country")
        self.setMinimumSize(740, 660)

        self.businesses: List[Dict]            = []
        self.worker:     Optional[ResearchWorker] = None
        self.session_calls: int                = 0

        self._build_ui()
        self._wire()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(12)

        # ── group: API key ──
        gKey = QGroupBox("API Key")
        vKey = QVBoxLayout(gKey)
        vKey.setSpacing(4)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Key:"))

        self.keyInput = QLineEdit()
        self.keyInput.setPlaceholderText("Paste your Serper.dev API key …")
        self.keyInput.setEchoMode(QLineEdit.Password)
        row1.addWidget(self.keyInput)

        self.btnTest = QPushButton("Test")
        self.btnTest.setFixedWidth(64)
        row1.addWidget(self.btnTest)
        vKey.addLayout(row1)

        # status line
        self.lblStatus = QLabel("Status:  —        |  Searches this session:  0")
        self.lblStatus.setStyleSheet("color:#7a756e; font-size:12px; margin-left:2px;")
        vKey.addWidget(self.lblStatus)

        root.addWidget(gKey)

        # ── group: search controls ────
        gSearch = QGroupBox("Search")
        vSearch = QVBoxLayout(gSearch)
        vSearch.setSpacing(6)

        rowIdea = QHBoxLayout()
        rowIdea.addWidget(QLabel("Business idea:"))
        self.ideaInput = QLineEdit()
        self.ideaInput.setPlaceholderText("e.g.  coffee shop, nail salon, gym (searches globally) …")
        rowIdea.addWidget(self.ideaInput)
        vSearch.addLayout(rowIdea)

        rowBtn = QHBoxLayout()
        rowBtn.addWidget(QLabel("Results:"))
        self.spinNum = QSpinBox()
        self.spinNum.setRange(1, 20)
        self.spinNum.setValue(5)
        self.spinNum.setFixedWidth(58)
        rowBtn.addWidget(self.spinNum)
        rowBtn.addStretch()

        self.btnSearch = QPushButton("Search")
        self.btnSearch.setFixedHeight(34)
        self.btnSearch.setStyleSheet(
            "QPushButton          { background-color:#2d5016; color:#fff;"
            "                       border-radius:5px; font-weight:600; font-size:13px; }"
            "QPushButton:hover    { background-color:#244010; }"
            "QPushButton:disabled { background-color:#9aab8e; }"
        )
        rowBtn.addWidget(self.btnSearch)
        vSearch.addLayout(rowBtn)

        root.addWidget(gSearch)

        # ── group: scrollable output ────
        gOut = QGroupBox("Output")
        vOut = QVBoxLayout(gOut)
        vOut.setContentsMargins(8, 8, 8, 8)
        vOut.setSpacing(6)

        self.outputView = QPlainTextEdit()
        self.outputView.setReadOnly(True)
        self.outputView.setPlaceholderText("Live progress and final results appear here …")

        mono = QFont("Consolas", 11)
        if not mono.exactMatch():
            mono = QFont("Courier New", 11)
        self.outputView.setFont(mono)
        vOut.addWidget(self.outputView)

        # export buttons
        rowExp = QHBoxLayout()
        rowExp.addStretch()
        self.btnJSON = QPushButton("Save JSON")
        self.btnCSV  = QPushButton("Save CSV")
        for b in (self.btnJSON, self.btnCSV):
            b.setEnabled(False)
            b.setFixedHeight(28)
            b.setStyleSheet(
                "QPushButton              { border:1px solid #bbb; border-radius:4px;"
                "                           padding:0 14px; font-size:12px; }"
                "QPushButton:hover:enabled{ border-color:#2d5016; color:#2d5016; }"
            )
        rowExp.addWidget(self.btnJSON)
        rowExp.addWidget(self.btnCSV)
        vOut.addLayout(rowExp)

        root.addWidget(gOut)
        root.setStretch(root.count() - 1, 1)  

    def _wire(self):
        self.btnTest.clicked.connect(self._test_key)
        self.btnSearch.clicked.connect(self._start_search)
        self.ideaInput.returnPressed.connect(self._start_search)  
        self.btnJSON.clicked.connect(self._export_json)
        self.btnCSV.clicked.connect(self._export_csv)

    def _test_key(self):
        key = self.keyInput.text().strip()
        if not key:
            self._set_status("paste a key first", "#7a756e")
            return

        self._set_status("testing …", "#7a756e")
        self.btnTest.setEnabled(False)

        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                json={"q": "test", "num": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                self._set_status("Key valid", "#2d5016", bold=True)
            elif resp.status_code == 429:
                self._set_status("Rate-limited – quota may be full", "#b07020")
            else:
                self._set_status(f"HTTP {resp.status_code}", "#c43c3c")
        except Exception as e:
            self._set_status(str(e)[:60], "#c43c3c")
        finally:
            self.btnTest.setEnabled(True)

    def _set_status(self, msg: str, color: str, bold: bool = False):
        w = "600" if bold else "400"
        self.lblStatus.setStyleSheet(
            f"color:{color}; font-size:12px; font-weight:{w}; margin-left:2px;"
        )
        self.lblStatus.setText(
            f"Status:  {msg}    |    Searches this session:  {self.session_calls}"
        )

    def _start_search(self):
        key  = self.keyInput.text().strip()
        idea = self.ideaInput.text().strip()

        if not key:
            self.outputView.appendPlainText("  ❌  Paste your API key first.")
            return
        if not idea:
            self.outputView.appendPlainText("  ❌  Type a business idea first.")
            return

        # reset output
        self.outputView.clear()
        self.businesses  = []
        self.btnJSON.setEnabled(False)
        self.btnCSV.setEnabled(False)
        self.btnSearch.setEnabled(False)

        # kick off worker
        self.worker = ResearchWorker(key, idea, self.spinNum.value())
        self.worker.log.connect(self._on_log)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_log(self, text: str):
        self.outputView.appendPlainText(text)
        self.outputView.verticalScrollBar().setValue(
            self.outputView.verticalScrollBar().maximum()
        )

    def _on_finished(self, businesses: List[Dict], api_calls: int):
        self.businesses = businesses
        self.session_calls += 1
        self._set_status("ready", "#2d5016", bold=True)

        self.btnSearch.setEnabled(True)
        self.btnJSON.setEnabled(True)
        self.btnCSV.setEnabled(True)

        # ── Display results ─────────────────────────────────────────
        self.outputView.appendPlainText("=" * 70)
        self.outputView.appendPlainText(
            f"  Found {len(businesses)} high-quality businesses "
            f"(4.0★+, 50+ reviews) | API calls: {api_calls}"
        )
        self.outputView.appendPlainText("=" * 70 + "\n")
        
        for biz in businesses:
            self.outputView.appendPlainText(
                f"  {biz['rank']}.  {biz['name']}  —  {biz['rating']}★ ({biz['review_count']:,} reviews)"
            )
            self.outputView.appendPlainText(f"      Website   :  {biz['website']}")
            self.outputView.appendPlainText(f"      Location  :  {biz['location']}")
            self.outputView.appendPlainText(f"      Maps      :  {biz['google_maps_link']}")
            self.outputView.appendPlainText("")

    def _on_error(self, msg: str):
        self.btnSearch.setEnabled(True)
        self.outputView.appendPlainText(f"\n  ❌  {msg}\n")

    def _export_json(self):
        if not self.businesses:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON", "results.json", "JSON (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.businesses, f, indent=2, ensure_ascii=False)
            self.outputView.appendPlainText(f"  💾  Saved JSON  →  {path}")

    def _export_csv(self):
        if not self.businesses:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "results.csv", "CSV (*.csv)"
        )
        if path:
            cols = ["rank","name","rating","review_count","website","location","google_maps_link","description"]
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                w.writeheader()
                w.writerows(self.businesses)
            self.outputView.appendPlainText(f"  💾  Saved CSV   →  {path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")                       

    pal = QPalette()
    pal.setColor(QPalette.Window,     QColor(244, 241, 236))  
    pal.setColor(QPalette.WindowText, QColor( 26,  24,  22))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
