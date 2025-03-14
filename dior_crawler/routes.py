from crawlee.crawlers import BeautifulSoupCrawlingContext
from crawlee.router import Router
import re

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
            images.append(img["src"])
    return images

def format_price(price_str):
    if not price_str or price_str == "Price not available":
        return None, None
    
    numeric_str = ''.join(filter(str.isdigit, price_str))
    currency = "VND" if "₫" in price_str else ""

    currency = currency.strip()
    
    return numeric_str if numeric_str else None, currency

def extract_product_details_dior(product_elem):
    try:
        # Extract product ID
        product_id = product_elem.get('data-object-id', '')
        
        # Extract images
        main_img = product_elem.select_one('img.main-asset')
        alt_img = product_elem.select_one('img.alt-asset')
        
        images = {
            "main": main_img['src'].split('?')[0] if main_img else "",  # Get clean URL without parameters
            "hover": alt_img['src'].split('?')[0] if alt_img else ""
        }

        # Extract product link
        link_elem = product_elem.select_one('a.product-card__link')
        link = link_elem['href'] if link_elem else ""
        
        # Extract name
        title_elem = product_elem.select_one('.title-wrapper span')
        name = clean_text(title_elem.text) if title_elem else ""
        
        # Extract description/color
        desc_elem = product_elem.select_one('.description-wrapper span')
        description = clean_text(desc_elem.text) if desc_elem else ""
        
        # Extract price
        price_elem = product_elem.select_one('.price-wrapper span')
        price_str = clean_text(price_elem.text) if price_elem else "Price not available"
        price_value, currency = format_price(price_str)
        
        variant_code = ""
        link_with_code = product_elem.select_one('a.MuiBox-root[href*="/products/"]')
        if link_with_code and 'href' in link_with_code.attrs:
            href = link_with_code['href']
            # Extract the code after /products/ from the href
            variant_code = href.split('/products/')[-1] if '/products/' in href else ""

        product_data = {
            "code": product_id,
            "name": name,
            "description": description,
            "price": price_value, 
            "currency": currency,  
            "imageUrl": images["main"],
            "sourceUrl": f"https://www.dior.com{link}" if link else "",
            "variants": [{
                "color": description, 
                "size": None,
                "code": variant_code,
                "price": price_value,
                "imageUrl": images["main"],
                "additionalImages": [images["hover"]] if images["hover"] else []
            }]
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
        products = soup.find_all("li", class_="MuiGrid-item")
    
        for product in products:
            
            try:
                product_data = extract_product_details_dior(product)
                if product_data and product_data["name"]:
                    base_name = product_data["name"]
                    
                    # If product already exists, append variant
                    if base_name in product_map:
                        if product_data["variants"][0] not in product_map[base_name]["variants"]:
                            product_map[base_name]["variants"].append(product_data["variants"][0])
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
