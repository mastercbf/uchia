# Uchia - Product Scraper Setup

## How to Make Scraping Actually Work

The browser can't directly scrape websites due to CORS security. You need to run a local backend server.

### Quick Start

1. **Open a terminal/command prompt**

2. **Navigate to where you saved the files**
   ```bash
   cd /path/to/your/files
   ```

3. **Install Python dependencies** (one time only)
   ```bash
   pip install flask flask-cors requests beautifulsoup4
   ```

4. **Start the scraper server**
   ```bash
   python uchia_scraper.py
   ```
   
   You should see:
   ```
   🚀 Uchia Scraper Server Starting...
   📍 Server running at: http://localhost:5000
   ```

5. **Open Uchia in your browser**
   - Open `uchia-bookmarklet.html` in your browser
   - The "Fetch Product Details" button will now work!

### How It Works

```
Your Browser (Uchia) → Python Server (localhost:5000) → Amazon/Other Sites
```

The Python server fetches and scrapes product pages, then sends the data back to your browser.

### What Gets Scraped

From Amazon product pages:
- ✅ Product title (`data-cel-widget="productTitle"`)
- ✅ Price (`a-price-whole`, `a-price-fraction`, `a-price-symbol`)
- ✅ Product image (Open Graph tags, landing image)

### Testing

1. Start the server (step 4 above)
2. Open Uchia in browser
3. Click "Add Gift"
4. Paste an Amazon URL
5. Click "Fetch Product Details"
6. Watch it auto-fill title, price, and image!

### Troubleshooting

**"Failed to fetch URL" error:**
- Make sure the Python server is running
- Check that it says "Server running at: http://localhost:5000"

**Server won't start:**
- Make sure Python is installed
- Install dependencies again: `pip install flask flask-cors requests beautifulsoup4`

**CORS errors in browser:**
- The server has CORS enabled, but make sure you're accessing Uchia via `file://` or `http://localhost`
