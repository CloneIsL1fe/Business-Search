# Business Competitor Research Tool

Desktop application to find high-quality business competitors using real Google Maps data.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- 🔍 **Smart Search** — Search any business type (coffee shops, nail salons, gyms, etc.)
- ⭐ **Quality Filter** — Auto-filters to 4+ star businesses only
- 📊 **Verified Reviews** — Requires 50+ reviews (reliable ratings)
- 🌐 **Website Verified** — Only businesses with listed websites
- 📍 **Real Addresses** — Actual locations from Google Maps
- 🚫 **Junk Blocked** — Filters out blogs, articles, social media, directories
- 💾 **Export Options** — Save results as JSON or CSV

## Screenshot
<img width="928" height="865" alt="image" src="https://github.com/user-attachments/assets/3a81ac95-8288-4482-9e9d-06c30540c6de" />
```

## Installation

### Requirements
- Python 3.10 or higher
- Windows, macOS, or Linux

### Setup

1. **Clone this repository:**
   ```bash
   git clone https://github.com/YOUR-USERNAME/business-competitor-research.git
   cd BUSINESS-SEARCH
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   ```

3. **Activate virtual environment:**
   ```bash
   # Windows
   .venv\Scripts\activate
   
   # macOS/Linux
   source .venv/bin/activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Get a free Serper.dev API key:**
   - Sign up at [serper.dev](https://serper.dev)
   - Get 2,500 free searches per month (no credit card required)
   - Copy your API key from the dashboard

## Usage

1. **Run the application:**
   ```bash
   python Business-Search.py
   ```

2. **Enter your Serper API key** in the "API Key" field

3. **Click "Test"** to verify your key works

4. **Type a business idea** (e.g., "yoga studio", "bakery", "barber shop")

5. **Choose how many results** you want (1-20)

6. **Click "Search"**

7. **Export results** to JSON or CSV if needed

## How It Works

### API
Uses [Serper.dev](https://serper.dev) which provides Google Maps/Places data via API:
- **Endpoint:** `/places` (returns ratings, reviews, addresses, websites)
- **Cost:** FREE for 2,500 searches/month
- **After free tier:** ~$50 per 5,000 searches

### Filters (applied automatically)
1. ✅ **Has website** — No blank website fields
2. ✅ **Not blacklisted** — Blocks Reddit, Facebook, blogs, news sites, etc.
3. ✅ **Rating ≥ 4.0 stars** — Only quality businesses
4. ✅ **Reviews ≥ 50** — Ensures reliable ratings (not 5★ from 3 reviews)

## File Structure

```
BUSINESS-SEARCH/
├── .gitignore                    # Excludes .venv, outputs, API keys
├── README.md                     # This file
├── requirements.txt              # Python dependencies
└── Business-Search.py   # Main application
```

## Dependencies

```
PySide6==6.8+         # GUI framework
requests==2.32+       # HTTP library
beautifulsoup4==4.12+ # HTML parsing (for blacklist validation)
```

Install all at once:
```bash
pip install -r requirements.txt
```

## Cost Breakdown

**At 75 searches/day (2,250/month):**
- Serper API: **$0** (within free tier of 2,500/month)

**After free tier:**
- $50 per 5,000 searches
- At 75/day = ~$6/month overage if you exceed 2,500

**Way cheaper than:**
- Google Places API (~$38/month for same volume)
- Hiring a VA to research manually

## Troubleshooting

### "DLL load failed while importing QtCore"
**Fix:**
```bash
pip install --force-reinstall --no-deps PySide6-Essentials
```

### "No businesses found matching..."
- Try a different search term
- Check your location (some areas have fewer results)
- Lower the review threshold by editing line 182 in the code:
  ```python
  MIN_REVIEWS = 50
  ```

### "API key is required"
- Make sure you pasted your actual Serper key (not the placeholder text)
- Get a new key at [serper.dev](https://serper.dev)

## Customization

Edit these constants in `Business-Search.py`:

```python
MIN_RATING = 4.0    # Change to 3.5, 4.5, etc.
MIN_REVIEWS = 100   # Change to 50, 200, etc.
```

Add more blacklisted domains:
```python
BLACKLISTED_DOMAINS = {
    "reddit.com",
    "your-domain-to-block.com",  # ← add here
    ...
}
```

## Contributing

Pull requests welcome! Please:
1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Personal Note

Feel free to take this code and use it for your own personal use.

## Support

- 📧 **Email:** jpmagbanua07@gmail.com

---
