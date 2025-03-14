from bs4 import BeautifulSoup
from crawlee.crawlers import BeautifulSoupCrawlingContext
from crawlee.router import Router
import re
import requests

router = Router[BeautifulSoupCrawlingContext]()

def extract_product_code(link):
    # Extract code from URL (e.g., "188423BF4.24VR" from the URL)
    match = re.search(r'[A-Z0-9]+\.[A-Z0-9]+(?=\.html)', link)
    return match.group(0) if match else None

def clean_text(text):
    if not text:
        return ""
    return ' '.join(text.strip().split())

def extract_detail_images(detail_soup):
    """Extract additional images from product detail page"""
    images = []
    img_container = detail_soup.find("div", class_="o-product__images")
    if img_container:
        for img in img_container.find_all("img"):
            if img.get("src"):
                images.append(img["src"])
    return images

def format_price(price_str):
    if not price_str or price_str == "Price not available":
        return None, None
    
    numeric_str = ''.join(filter(str.isdigit, price_str))
    currency = "VND" if "₫" in price_str else ""
    currency = currency.strip()
    
    return numeric_str if numeric_str else None, currency

def extract_product_details(detail_soup):
    """Extract product description and details from accordion sections"""
    details = {
        "description": "",
        "details": ""
    }
    
    accordion = detail_soup.find("ul", class_="o-product__descriptions")
    if accordion:
        for item in accordion.find_all("li", class_="m-accordion__item"):
            title = item.find("button").text.strip().lower() if item.find("button") else ""
            content = item.find("div", class_="a-text").text.strip() if item.find("div", class_="a-text") else ""
            
            if "description" in title:
                details["description"] = content
            elif "details" in title:
                details["details"] = content
                
    return details

def extract_product_details_celine(product, url):
    """Extract all product details from a product page"""
    try:
        # Fetch the product detail page
        full_url = f"https://www.celine.com{url}" if not url.startswith("http") else url
        detail_response = requests.get(full_url)
        detail_soup = BeautifulSoup(detail_response.content, 'html.parser')
        
        # Get product details from accordion
        details_data = extract_product_details(detail_soup)
        
        # Extract product name
        name_elem = detail_soup.find("span", class_="o-product__title-truncate f-body")
        name = clean_text(name_elem.text) if name_elem else ""
        
        # Skip if no name
        if not name:
            return None
            
        # Split name and color variant
        name_parts = name.split(';') if ';' in name else [name, ""]
        base_name = name_parts[0].strip()
        
        # Get color variant
        color_elem = detail_soup.find("p", class_="m-selector__title")
        color_variant = clean_text(color_elem.text) if color_elem else ""
        
        # Get product code
        product_code = extract_product_code(url)
        
        # Get product ID
        product_id = detail_soup.find("section", class_="o-product product-detail")
        product_id = product_id["data-pid"] if product_id and "data-pid" in product_id.attrs else product_code or ""
        
        # Get images
        img_container = product.find("div", class_="m-product-listing__img-img")
        main_img = img_container.find("img", {"data-image-type": "main"}) if img_container else None
        hover_img = img_container.find("img", {"data-image-type": "hover"}) if img_container else None
        
        images = {
            "main": main_img["src"] if main_img and "src" in main_img.attrs else "",
            "hover": hover_img["src"] if hover_img and "src" in hover_img.attrs else ""
        }
        
        # Get additional images from detail page
        additional_images = extract_detail_images(detail_soup)
        
        # Get price
        price_elem = product.find("span", class_="prices")
        price_value, currency = format_price(price_elem.text) if price_elem else (None, None)
        
        # Skip if no price
        if not price_value:
            return None
        
        # Create product data structure
        product_data = {
            "code": product_id or product_code,
            "name": base_name,
            "details": details_data["details"],
            "description": details_data["description"],
            "price": price_value,
            "currency": currency,
            "imageUrl": images["main"],
            "additionalImages": additional_images,
            "variants": [{
                "color": color_variant,
                "size": None,
                "price": price_value,
                "code": product_code,
                "imageUrl": images["main"],
                "additionalImages": additional_images
            }],
            "sourceUrl": full_url
        }
        
        return product_data
    except Exception as e:
        print(f"Error processing product: {e}")
        return None

@router.default_handler
async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
    context.log.info(f'Processing {context.request.url} ...')

    if context.http_response.status_code == 200:
        soup = context.soup
        product_map = {}  
        products = soup.find_all("li", class_="o-listing-grid__item")
    
        for product in products:
            try:
                # Get product link
                link_elem = product.find("a")
                if not link_elem or "href" not in link_elem.attrs:
                    continue
                    
                link = link_elem["href"]
                
                # Extract product data
                product_data = extract_product_details_celine(product, link)
                
                if product_data and product_data["name"]:
                    base_name = product_data["name"]
                    
                    # If product already exists, append variant
                    if base_name in product_map:
                        # Add variant if it doesn't exist
                        variant_codes = [v["code"] for v in product_map[base_name]["variants"]]
                        if product_data["variants"][0]["code"] not in variant_codes:
                            product_map[base_name]["variants"].append(product_data["variants"][0])
                        
                        # Add new images to additionalImages if they don't exist
                        product_map[base_name]["additionalImages"].extend(
                            img for img in product_data["additionalImages"] 
                            if img not in product_map[base_name]["additionalImages"]
                        )
                    else:
                        # Create new product entry
                        product_map[base_name] = product_data
                
            except Exception as e:
                print(f"Error processing product: {e}")

        # Convert product_map to list for final output
        product_data = list(product_map.values())
        await context.push_data(
        {
            'brand': 'dior',
            'products': product_data
        })
    else:
        context.log.error(f'Error processing {context.request.url} ...')
        # print(json.dumps({"brand":"dior","products": product_data}, indent=4, ensure_ascii=False))
    """Default request handler."""
    # title = context.soup.find('title')
    

    await context.enqueue_links()
