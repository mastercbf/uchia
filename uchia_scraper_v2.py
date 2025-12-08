from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import json as json_lib

app = Flask(__name__)
CORS(app)

def scrape_with_requests(url, max_retries=3):
    """Try scraping with simple requests first, with retries"""
    import time
    import random
    
    headers = {
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
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = random.uniform(2, 4)  # Random delay between 2-4 seconds
                print(f"⏳ Waiting {wait_time:.1f} seconds before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            
            print(f"🌐 Fetching page (attempt {attempt + 1}/{max_retries})...")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            print(f"✅ Page fetched (status: {response.status_code}, size: {len(response.text)} bytes)")
            
            # Check if we got a real page or a bot detection page
            html_lower = response.text.lower()
            if 'sorry, we just need to make sure' in html_lower or 'robot' in html_lower[:1000]:
                print(f"🤖 Bot detection page detected on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    print("❌ All attempts resulted in bot detection")
            
            # Save HTML for debugging
            import os
            debug_path = os.path.expanduser('~/amazon_debug.html')
            try:
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"💾 HTML saved to {debug_path} for inspection")
            except Exception as e:
                print(f"⚠️ Could not save debug HTML: {e}")
            
            return response.text
            
        except requests.RequestException as e:
            print(f"❌ Request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                continue
            else:
                raise
    
    return None

def extract_data(html, url):
    """Extract product data from HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    
    result = {
        'title': None,
        'price': None,
        'imageUrl': None
    }
    
    # ===== EXTRACT TITLE =====
    print("\n🔍 Searching for title...")
    
    # Method 1: data-cel-widget="productTitle"
    title_elem = soup.find('span', {'data-cel-widget': 'productTitle'})
    if title_elem:
        result['title'] = title_elem.get_text(strip=True)
        print(f"✅ Title found (data-cel-widget): {result['title'][:60]}...")
    
    # Method 2: id="productTitle"
    if not result['title']:
        title_elem = soup.find(id='productTitle')
        if title_elem:
            result['title'] = title_elem.get_text(strip=True)
            print(f"✅ Title found (id): {result['title'][:60]}...")
    
    # Method 3: Open Graph title
    if not result['title']:
        og_title = soup.find('meta', property='og:title')
        if og_title:
            result['title'] = og_title.get('content', '').strip()
            print(f"✅ Title found (og:title): {result['title'][:60]}...")
    
    # Method 4: Twitter title
    if not result['title']:
        twitter_title = soup.find('meta', {'name': 'twitter:title'})
        if twitter_title:
            result['title'] = twitter_title.get('content', '').strip()
            print(f"✅ Title found (twitter:title): {result['title'][:60]}...")
    
    # Method 5: title tag
    if not result['title']:
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Remove "Amazon.com: " and " : ..." parts
            title_clean = re.sub(r'^Amazon\.com:\s*', '', title_text)
            title_clean = title_clean.split(':')[0].strip()
            
            # Only use if it's not just "Amazon.com"
            if title_clean and title_clean.lower() not in ['amazon.com', 'amazon']:
                result['title'] = title_clean
                print(f"✅ Title found (title tag): {result['title'][:60]}...")
            else:
                print(f"⚠️ Title tag was generic: '{title_clean}' - skipping")
    
    # Method 6: h1 with product title
    if not result['title']:
        h1_elem = soup.find('h1', class_=re.compile('product|title', re.I))
        if h1_elem:
            result['title'] = h1_elem.get_text(strip=True)
            print(f"✅ Title found (h1): {result['title'][:60]}...")
    
    # Method 7: Any h1 as last resort
    if not result['title']:
        h1_elem = soup.find('h1')
        if h1_elem:
            h1_text = h1_elem.get_text(strip=True)
            if h1_text and len(h1_text) > 10:  # Must be substantial
                result['title'] = h1_text
                print(f"✅ Title found (h1 fallback): {result['title'][:60]}...")
    
    if not result['title']:
        print("❌ Title not found - Amazon may be blocking the scraper")
    
    # ===== EXTRACT PRICE =====
    print("\n🔍 Searching for price...")
    
    if 'amazon.com' in url:
        # Method 1: Standard a-price structure
        price_whole = soup.find('span', class_='a-price-whole')
        price_fraction = soup.find('span', class_='a-price-fraction')
        
        if price_whole:
            whole = re.sub(r'[^0-9]', '', price_whole.get_text(strip=True))
            fraction = price_fraction.get_text(strip=True) if price_fraction else '00'
            result['price'] = f"${whole}.{fraction}"
            print(f"✅ Price found (a-price): {result['price']}")
        
        # Method 2: Look for price in apexPriceToPay
        if not result['price']:
            apex_price = soup.find('span', class_='a-price')
            if apex_price:
                offscreen = apex_price.find('span', class_='a-offscreen')
                if offscreen:
                    result['price'] = offscreen.get_text(strip=True)
                    print(f"✅ Price found (a-offscreen): {result['price']}")
        
        # Method 3: Search all text for price patterns
        if not result['price']:
            price_elements = soup.find_all('span', class_=re.compile('price|Price'))
            for elem in price_elements:
                text = elem.get_text(strip=True)
                match = re.search(r'\$\d+[.,]\d{2}', text)
                if match:
                    result['price'] = match.group(0)
                    print(f"✅ Price found (regex): {result['price']}")
                    break
        
        # Method 4: JSON-LD structured data
        if not result['price']:
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json_lib.loads(script.string)
                    if isinstance(data, dict):
                        if 'offers' in data:
                            offers = data['offers']
                            if isinstance(offers, dict) and 'price' in offers:
                                result['price'] = f"${offers['price']}"
                                print(f"✅ Price found (JSON-LD): {result['price']}")
                                break
                except:
                    pass
    
    if not result['price']:
        print("❌ Price not found")
    
    # ===== EXTRACT IMAGE =====
    print("\n🔍 Searching for image...")
    
    # Method 1: Open Graph image
    og_image = soup.find('meta', property='og:image')
    if og_image:
        result['imageUrl'] = og_image.get('content')
        print(f"✅ Image found (og:image): {result['imageUrl'][:60]}...")
    
    # Method 2: landingImage
    if not result['imageUrl']:
        landing_img = soup.find('img', id='landingImage')
        if landing_img:
            src = landing_img.get('src') or landing_img.get('data-old-hires') or landing_img.get('data-a-dynamic-image')
            if src:
                # Handle dynamic image JSON
                if src.startswith('{'):
                    try:
                        img_data = json_lib.loads(src)
                        result['imageUrl'] = list(img_data.keys())[0]
                    except:
                        pass
                else:
                    result['imageUrl'] = src
                print(f"✅ Image found (landingImage): {result['imageUrl'][:60]}...")
    
    # Method 3: imgTagWrapperId
    if not result['imageUrl']:
        img_wrapper = soup.find('div', id='imgTagWrapperId')
        if img_wrapper:
            img = img_wrapper.find('img')
            if img:
                result['imageUrl'] = img.get('src') or img.get('data-old-hires')
                if result['imageUrl']:
                    print(f"✅ Image found (imgTagWrapper): {result['imageUrl'][:60]}...")
    
    # Method 4: altImages
    if not result['imageUrl']:
        alt_images = soup.find('div', id='altImages')
        if alt_images:
            imgs = alt_images.find_all('img')
            for img in imgs:
                src = img.get('src', '')
                if 'images-amazon.com/images/I/' in src:
                    result['imageUrl'] = src.replace('_AC_US40_', '_AC_SL1500_')
                    print(f"✅ Image found (altImages): {result['imageUrl'][:60]}...")
                    break
    
    # Method 5: Any large Amazon product image
    if not result['imageUrl']:
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            if 'images-amazon.com/images/I/' in src and ('_AC_' in src or '_SL' in src):
                result['imageUrl'] = src
                print(f"✅ Image found (product img): {result['imageUrl'][:60]}...")
                break
    
    # Method 6: Twitter card image
    if not result['imageUrl']:
        twitter_image = soup.find('meta', {'name': 'twitter:image'})
        if twitter_image:
            result['imageUrl'] = twitter_image.get('content')
            print(f"✅ Image found (twitter:image): {result['imageUrl'][:60]}...")
    
    if not result['imageUrl']:
        print("❌ Image not found")
    
    return result

@app.route('/api/scrape', methods=['POST'])
def scrape_product():
    try:
        data = request.json
        url = data.get('url')
        
        print(f"\n" + "="*80)
        print(f"📥 NEW SCRAPE REQUEST")
        print(f"🔗 URL: {url}")
        print("="*80)
        
        if not url:
            print("❌ No URL provided")
            return jsonify({'error': 'No URL provided'}), 400
        
        # Fetch HTML
        html = scrape_with_requests(url)
        
        # Extract data
        result = extract_data(html, url)
        
        print("\n" + "="*80)
        print("📊 SCRAPING RESULTS:")
        print(f"  Title: {'✅ Found' if result['title'] else '❌ Not found'}")
        print(f"  Price: {'✅ Found' if result['price'] else '❌ Not found'}")
        print(f"  Image: {'✅ Found' if result['imageUrl'] else '❌ Not found'}")
        print("="*80 + "\n")
        
        return jsonify(result)
        
    except requests.RequestException as e:
        print(f"❌ Request error: {str(e)}")
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 500
    except Exception as e:
        print(f"❌ Scraping error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Scraping error: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 UCHIA SCRAPER SERVER")
    print("="*80)
    print("📍 Server URL: http://localhost:5000")
    print("✅ Ready to scrape Amazon products!")
    print("="*80 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
