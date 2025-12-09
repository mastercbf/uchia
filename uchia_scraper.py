from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import random

app = Flask(__name__)
CORS(app)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 15
RETRY_DELAY_MIN = 2
RETRY_DELAY_MAX = 4

USER_AGENT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0'
}

def fetch_page(url):
    """Fetch HTML from URL with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                wait_time = random.uniform(RETRY_DELAY_MIN, RETRY_DELAY_MAX)
                time.sleep(wait_time)

            response = requests.get(url, headers=USER_AGENT_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            html_lower = response.text.lower()
            if 'sorry, we just need to make sure' in html_lower or 'robot' in html_lower[:1000]:
                if attempt < MAX_RETRIES - 1:
                    continue

            return response.text

        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise

    return None

def extract_title(soup):
    """Extract product title from HTML soup"""
    title_elem = soup.find('span', {'data-cel-widget': 'productTitle'})
    if title_elem:
        return title_elem.get_text(strip=True)

    title_elem = soup.find(id='productTitle')
    if title_elem:
        return title_elem.get_text(strip=True)

    og_title = soup.find('meta', property='og:title')
    if og_title:
        return og_title.get('content', '').strip()

    twitter_title = soup.find('meta', {'name': 'twitter:title'})
    if twitter_title:
        return twitter_title.get('content', '').strip()

    title_tag = soup.find('title')
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        title_clean = re.sub(r'^Amazon\.com:\s*', '', title_text)
        title_clean = title_clean.split(':')[0].strip()
        if title_clean and title_clean.lower() not in ['amazon.com', 'amazon']:
            return title_clean

    h1_elem = soup.find('h1', class_=re.compile('product|title', re.I))
    if h1_elem:
        return h1_elem.get_text(strip=True)

    h1_elem = soup.find('h1')
    if h1_elem:
        h1_text = h1_elem.get_text(strip=True)
        if h1_text and len(h1_text) > 10:
            return h1_text

    return None

def extract_price(soup, url):
    """Extract product price from HTML soup"""
    if 'amazon.com' not in url:
        return None

    price_whole = soup.find('span', class_='a-price-whole')
    price_fraction = soup.find('span', class_='a-price-fraction')
    if price_whole:
        whole = re.sub(r'[^0-9]', '', price_whole.get_text(strip=True))
        fraction = price_fraction.get_text(strip=True) if price_fraction else '00'
        return f"${whole}.{fraction}"

    apex_price = soup.find('span', class_='a-price')
    if apex_price:
        offscreen = apex_price.find('span', class_='a-offscreen')
        if offscreen:
            return offscreen.get_text(strip=True)

    price_elements = soup.find_all('span', class_=re.compile('price|Price'))
    for elem in price_elements:
        text = elem.get_text(strip=True)
        match = re.search(r'\$\d+[.,]\d{2}', text)
        if match:
            return match.group(0)

    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and 'offers' in data:
                offers = data['offers']
                if isinstance(offers, dict) and 'price' in offers:
                    return f"${offers['price']}"
        except:
            pass

    return None

def extract_image(soup):
    """Extract product image URL from HTML soup"""
    og_image = soup.find('meta', property='og:image')
    if og_image:
        return og_image.get('content')

    landing_img = soup.find('img', id='landingImage')
    if landing_img:
        src = landing_img.get('src') or landing_img.get('data-old-hires') or landing_img.get('data-a-dynamic-image')
        if src:
            if src.startswith('{'):
                try:
                    img_data = json.loads(src)
                    return list(img_data.keys())[0]
                except:
                    pass
            else:
                return src

    img_wrapper = soup.find('div', id='imgTagWrapperId')
    if img_wrapper:
        img = img_wrapper.find('img')
        if img:
            image_url = img.get('src') or img.get('data-old-hires')
            if image_url:
                return image_url

    alt_images = soup.find('div', id='altImages')
    if alt_images:
        imgs = alt_images.find_all('img')
        for img in imgs:
            src = img.get('src', '')
            if 'images-amazon.com/images/I/' in src:
                return src.replace('_AC_US40_', '_AC_SL1500_')

    images = soup.find_all('img')
    for img in images:
        src = img.get('src', '')
        if 'images-amazon.com/images/I/' in src and ('_AC_' in src or '_SL' in src):
            return src

    twitter_image = soup.find('meta', {'name': 'twitter:image'})
    if twitter_image:
        return twitter_image.get('content')

    return None

def extract_data(html, url):
    """Extract product data from HTML"""
    soup = BeautifulSoup(html, 'html.parser')

    return {
        'title': extract_title(soup),
        'price': extract_price(soup, url),
        'imageUrl': extract_image(soup)
    }

@app.route('/api/scrape', methods=['POST'])
def scrape_product():
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        html = fetch_page(url)
        result = extract_data(html, url)

        return jsonify(result)

    except requests.RequestException as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Scraping error: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print("🚀 Uchia Scraper Server Starting...")
    print("📍 Server URL: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
