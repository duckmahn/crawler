from crawlee.crawlers import BeautifulSoupCrawlingContext
from crawlee.router import Router
import re
import json
import os  # Thêm import os

router = Router[BeautifulSoupCrawlingContext]()

def extract_product_code(link):
    # Extract code from URL (e.g., "188423BF4.24VR" from the URL)
    match = re.search(r'[A-Z0-9]+\.[A-Z0-9]+(?=\.html)', link)
    return match.group(0) if match else None

def clean_text(text):
    if not text:
        return ""
    return ' '.join(text.strip().split())

# def extract_detail_images(detail_soup):
#     """Extract additional images from product detail page"""
#     images = []
#     img_container = detail_soup.find("div", class_="o-product__images")
#     if img_container:
#         for img in img_container.find_all("img"):
#             images.append(img["src"])
#     return images

def format_price(price_str):
    if not price_str or price_str == "Price not avextract_product_details_diorailable":
        return None, None
    
    numeric_str = ''.join(filter(str.isdigit, price_str))
    currency = "VND" if "₫" in price_str else ""

    currency = currency.strip()
    
    return numeric_str if numeric_str else None, currency

async def fetch_variant_details(context, variant_url, parent_product):
    """
    Fetch detailed information about a specific product variant by following its link
    """
    if not variant_url:
        return None
    
    print(f"Fetching variant details from: {variant_url}")
    
    # Extract variant code from the URL
    variant_code = ""
    if "/products/" in variant_url:
        variant_code = variant_url.split("/products/")[-1]
    
    try:
        # Use Python's requests library to fetch the page in a non-blocking way
        import requests
        import asyncio
        from bs4 import BeautifulSoup
        
        # Run the synchronous requests call in a thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.get(variant_url, timeout=30)
        )
        
        if not response or response.status_code != 200:
            print(f"Failed to fetch variant page: {variant_url}")
            return None
            
        # Parse the HTML with BeautifulSoup
        variant_soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract color information from the heading element
        color_info = ""
        color_element = variant_soup.select_one('h2.MuiTypography-root.MuiTypography-body-s.DS-Typography')
        if color_element:
            color_info = clean_text(color_element.text)
            print(f"Found variant color: {color_info}")
        
        # Extract price information
        price_value = None
        currency = None
        price_element = variant_soup.select_one('.ProductPrice-module_formattedPrice__OX9TS')
        if price_element:
            price_str = clean_text(price_element.text)
            price_value, currency = format_price(price_str)
        
        # Extract variant-specific images
        variant_images = []
        
        # Try to find main image first
        primary_image = ""
        # Try to find the main image first - using specific classes
        main_img_selectors = [
            'img.MuiBox-root.mui-latin-1rljeqr',  # Primary target class
            '.ProductImageMainDisplay img',  # Main product image
            '.swiper-slide-active img',  # Active slide in a carousel
            '.ProductDesktopSlider img:first-child'  # First image in desktop slider
        ]
        
        for selector in main_img_selectors:
            main_img = variant_soup.select_one(selector)
            if main_img and 'src' in main_img.attrs:
                primary_image = main_img['src'].split('?')[0]
                break
        
        # Convert variant code to format that appears in image URLs (removing underscore)
        url_variant_code = variant_code.replace('_', '') if '_' in variant_code else variant_code
        
        # Try multiple selectors to find product images
        image_selectors = [
            'img.MuiBox-root',
            '.ProductImageTab img',
            '.ProductImageCinematicDisplay img',
            '.swiper-slide img',
            '.ProductDesktopSlider img',
            'img[srcset]'
        ]
        
        for selector in image_selectors:
            image_elements = variant_soup.select(selector)
            for img in image_elements:
                if 'src' in img.attrs:
                    img_src = img['src'].split('?')[0]  # Get clean URL without parameters
                    
                    if img_src and img_src not in variant_images and 'dior' in img_src.lower():
                        # Only include images with the exact variant code
                        if url_variant_code and url_variant_code in img_src:
                            variant_images.append(img_src)
        
        print(f"Found {len(variant_images)} images for variant {variant_code}")
        
        # If we couldn't find a primary image but have other images, use the first one
        if not primary_image and variant_images:
            primary_image = variant_images[0]
        
        # Check for available sizes if any
        sizes = []
        size_elements = variant_soup.select('.ProductSizes-module_productSizes__sizeWrapper__XPR6S button')
        for size_elem in size_elements:
            size_text = clean_text(size_elem.text)
            if size_text:
                sizes.append(size_text)
        
        # Build the variant data structure
        variant_data = {
            "code": variant_code,
            "color": color_info if color_info else parent_product.get("description", ""),
            "price": price_value if price_value else parent_product.get("price"),
            "currency": currency if currency else parent_product.get("currency"),
            "imageUrl": primary_image or (variant_images[0] if variant_images else parent_product.get("imageUrl", "")),
            "additionalImages": variant_images,
            "sourceUrl": variant_url,
            "sizes": sizes if sizes else None
        }
        
        return variant_data
        
    except Exception as e:
        print(f"Error fetching variant details: {e}")
        return None

async def extract_product_dior(context):
    """Extract all available information for a dior.com product URL"""
    from flask import request
    import json
    import os
    from bs4 import BeautifulSoup
    import asyncio
    
    url = request.json.get('url')
    
    if not url:
        return {"error": "No URL provided"}
    
    try:
        # Get product details
        product_details = await get_product_detail(context, url)
        if not product_details:
            return {"error": "Failed to fetch product details"}
        
        # Get source_url and image_url from the initial product data
        source_url = url
        variant_code = ""
        
        # Extract variant code from the URL
        if "/products/" in source_url:
            variant_code = source_url.split("/products/")[-1]
        
        # Get primary image if available, otherwise use first additional image
        primary_image = ""
        additional_images = product_details.get("additionalImages", [])
        if additional_images and len(additional_images) > 0:
            primary_image = additional_images[0]
        
        # Get the base product data from the request
        product_data = {
            "retailer": "dior",
            "brand": "Dior",
            "title": product_details.get("title", ""),
            "description": product_details.get("description", ""),
            "price": product_details.get("price", ""),
            "currency": product_details.get("currency", ""),
            "imageUrl": primary_image,  # Use the first image as primary
            "productId": product_details.get("product_id", ""),
            "sourceUrl": source_url,
            "variantId": variant_code,
            "colorInfo": product_details.get("colorInfo", ""),
            "variants": [],
            "additionalImages": additional_images
        }

        # Add the current variant to the variants array
        current_variant = {
            "code": variant_code,
            "color": product_details.get("colorInfo", "") or product_data.get("description", ""),
            "price": product_data.get("price"),
            "currency": product_data.get("currency"),
            "imageUrl": primary_image,  # Use the first image as primary
            "additionalImages": additional_images,  # Use all images as additional
            "sourceUrl": source_url
        }
        
        # Add the current variant to the variants array
        product_data["variants"].append(current_variant)
        
        # Check if there are other variants to process
        variant_urls = product_details.get("variants", [])
        
        # Initialize an array to store variant fetch tasks
        variant_tasks = []
        
        # Fetch details for each variant
        for variant_url in variant_urls:
            if variant_url != source_url:  # Skip the current URL
                task = fetch_variant_details(context, variant_url, product_data)
                variant_tasks.append(task)
        
        # Wait for all variant fetches to complete
        if variant_tasks:
            variant_results = await asyncio.gather(*variant_tasks)
            # Add all successfully fetched variants to the product data
            for variant_result in variant_results:
                if variant_result:
                    product_data["variants"].append(variant_result)
        
        # Save the product data to a file
        storage_dir = os.path.join('storage', 'dior')
        os.makedirs(storage_dir, exist_ok=True)
        
        file_name = f"dior-prd-{variant_code}.json"
        file_path = os.path.join(storage_dir, file_name)
        
        with open(file_path, 'w') as f:
            json.dump(product_data, f, indent=2)
        
        return {"success": True, "data": product_data}
    except Exception as e:
        print(f"Error processing product: {e}")
        return {"error": "An error occurred while processing the product"}

def extract_product_dior_detail(product_elem):
    try:
        # Extract product ID
        product_id = product_elem.get('data-object-id', '') 
        product_data = {
            "brand": "dior",
            "code": product_id,
            "name": "",
            "description": "",
            "price": "",
                "currency": "",
            "imageUrl": "",
            "sourceUrl": "",
            "variants": []
        }
        return product_data
    except Exception as e:
        print(f"Error processing product: {e}")
        return None

async def get_product_detail(context, url):
    """Fetch detailed information for a specific product URL"""
    try:
        import requests
        import asyncio
        from bs4 import BeautifulSoup
        
        print(f"Fetching product details from: {url}")
        
        # Run the synchronous requests call in a thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.get(url, timeout=30)
        )
        
        if not response or response.status_code != 200:
            print(f"Failed to fetch detail page: {url}")
            return None
        
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the product title
        title = ""
        title_elem = soup.select_one('h1.MuiTypography-root')
        if title_elem:
            title = clean_text(title_elem.text)
        
        # Extract full product description
        full_description = ""
        desc_elements = soup.select('div.MuiAccordionDetails-root p')
        for elem in desc_elements:
            if elem.text.strip():
                full_description += clean_text(elem.text) + " "
        
        # Extract price information
        price_value = None
        currency = None
        price_element = soup.select_one('.ProductPrice-module_formattedPrice__OX9TS')
        if price_element:
            price_str = clean_text(price_element.text)
            price_value, currency = format_price(price_str)
        
        # Extract product ID
        product_id = ""
        product_id_meta = soup.select_one('meta[property="product:retailer_item_id"]')
        if product_id_meta and 'content' in product_id_meta.attrs:
            product_id = product_id_meta['content']
        
        # Extract variant code from the URL
        variant_code = ""
        if "/products/" in url:
            variant_code = url.split("/products/")[-1]
        
        # Try to find main image first
        primary_image = ""
        # Try to find the main image first - using specific classes
        main_img_selectors = [
            'img.MuiBox-root.mui-latin-1rljeqr',  # Primary target class
            '.ProductImageMainDisplay img',  # Main product image
            '.swiper-slide-active img',  # Active slide in a carousel
            '.ProductDesktopSlider img:first-child'  # First image in desktop slider
        ]
        
        for selector in main_img_selectors:
            main_img = soup.select_one(selector)
            if main_img and 'src' in main_img.attrs:
                primary_image = main_img['src'].split('?')[0]
                break
        
        # Convert variant code to format that appears in image URLs (removing underscore)
        url_variant_code = variant_code.replace('_', '') if '_' in variant_code else variant_code
        
        # Try multiple selectors to find product images
        additional_images = []
        image_selectors = [
            'img.MuiBox-root',
            '.ProductImageTab img',
            '.ProductImageCinematicDisplay img',
            '.swiper-slide img',
            '.ProductDesktopSlider img',
            'img[srcset]'
        ]
        
        for selector in image_selectors:
            image_elements = soup.select(selector)
            for img in image_elements:
                if 'src' in img.attrs:
                    img_src = img['src'].split('?')[0]  # Get clean URL without parameters
                    
                    if img_src and img_src not in additional_images and 'dior' in img_src.lower():
                        # Only include images with the exact variant code
                        if url_variant_code and url_variant_code in img_src:
                            print(f"Including image with variant code {url_variant_code}: {img_src}")
                            additional_images.append(img_src)
        
        # If we have a primary image but it's not in additional_images, add it
        if primary_image and primary_image not in additional_images:
            additional_images.insert(0, primary_image)
            
        # If we couldn't find a primary image but have other images, use the first one
        if not primary_image and additional_images:
            primary_image = additional_images[0]
            
        print(f"Found {len(additional_images)} images for product {variant_code}")
        
        # Extract color information from the heading element
        color_info = ""
        color_element = soup.select_one('h2.MuiTypography-root.MuiTypography-body-s.DS-Typography')
        if color_element:
            color_info = clean_text(color_element.text)
            print(f"Found color info: {color_info}")
        
        # Extract other variant links
        variant_links = []
        variant_elements = soup.select('.ProductVariants-module_productColorVariants__jd2fl a')
        for variant_elem in variant_elements:
            if 'href' in variant_elem.attrs:
                variant_href = variant_elem['href']
                if variant_href and variant_href.startswith('/'):
                    full_variant_url = f"https://www.dior.com{variant_href}"
                    if full_variant_url != url:  # Don't include the current URL
                        variant_links.append(full_variant_url)
        
        return {
            "title": title,
            "description": title,
            "fullDescription": full_description.strip(),
            "price": price_value,
            "currency": currency,
            "product_id": product_id,
            "imageUrl": primary_image,
            "additionalImages": additional_images,
            "colorInfo": color_info,
            "variants": variant_links
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error fetching product details: {e}")
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
                # Extract product details from the list page
                product_data = await extract_product_listing(context, product)
                if product_data and product_data["code"]:
                    base_name = product_data["name"]
                    
                    # If product already exists, append variant
                    if base_name in product_map:
                        if product_data["variants"][0] not in product_map[base_name]["variants"]:
                            product_map[base_name]["variants"].append(product_data["variants"][0])
                    else:
                        # Create new product entry
                        product_map[base_name] = product_data
                        
                        # Create directory for the brand in the storage folder
                        brand_folder = os.path.join('storage', product_data['brand'])
                        os.makedirs(brand_folder, exist_ok=True)  # Create directory if it doesn't exist

                        # Export product to a file named product.brand - product.code
                        if product_data["code"]:
                            file_name = f"{product_data['brand']}-{product_data['code']}.json"
                            file_path = os.path.join(brand_folder, file_name)  # File path
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(product_data, f, ensure_ascii=False, indent=4)
                
            except Exception as e:
                print(f"Error processing product: {e}")

    else:
        context.log.error(f'Error processing {context.request.url} ...')

    await context.enqueue_links()

async def extract_product_listing(context, product_elem):
    """Extract product data from the product listing page"""
    try:
        # Extract product ID
        product_id = product_elem.get('data-object-id', '')
        
        # Extract images
        main_img = product_elem.select_one('img.main-asset')
        alt_img = product_elem.select_one('img.alt-asset')
        
        # Try to find main image from MuiBox-root mui-latin-1rljeqr or main-asset
        primary_image = ""
        mui_box_img = product_elem.select_one('img.MuiBox-root.mui-latin-1rljeqr')
        if mui_box_img and 'src' in mui_box_img.attrs:
            primary_image = mui_box_img['src'].split('?')[0]
        elif main_img and 'src' in main_img.attrs:
            primary_image = main_img['src'].split('?')[0]
            
        images = {
            "main": primary_image or (main_img['src'].split('?')[0] if main_img else ""),  # Get clean URL without parameters
            "hover": alt_img['src'].split('?')[0] if alt_img else ""
        }

        # Extract additional images with class "MuiBox-root mui-latin-ot5e1e"
        additional_img_elements = product_elem.select('img.MuiBox-root')
        additional_images = []
        
        for img in additional_img_elements:
            if 'src' in img.attrs:
                img_src = img['src'].split('?')[0]  # Get clean URL without parameters
                if img_src and img_src not in additional_images:
                    additional_images.append(img_src)
                    
        # Add main image to the additional_images array if not already there
        if images["main"] and images["main"] not in additional_images:
            additional_images.insert(0, images["main"])

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
            "brand": "dior",
            "code": product_id,
            "name": name,
            "description": description,
            "price": price_value, 
            "currency": currency,  
            "imageUrl": images["main"],  # Set single primary image as imageUrl
            "additionalImages": additional_images,  # Set all images as additionalImages
            "sourceUrl": f"https://www.dior.com{link}" if link else "",
            "variants": [{
                "color": description, 
                "size": None,
                "code": variant_code,
                "price": price_value,
                "imageUrl": images["main"],  # Set single primary image as imageUrl
                "additionalImages": additional_images  # Set all images as additionalImages
            }]
        }
        
        # Fetch additional details from the product page if sourceUrl exists
        if product_data["sourceUrl"]:
            # Now we can directly await the async function since we're in an async function
            detail_data = await get_product_detail(context, product_data["sourceUrl"])
            
            if detail_data:
                # Update product data with detailed information
                if detail_data["additionalImages"] and len(detail_data["additionalImages"]) > 0:
                    # Set additionalImages from detail page
                    product_data["additionalImages"] = detail_data["additionalImages"]
                    product_data["variants"][0]["additionalImages"] = detail_data["additionalImages"]
                    
                    # Set imageUrl to the first detailed image if main image is not set
                    if not product_data["imageUrl"] and len(detail_data["additionalImages"]) > 0:
                        product_data["imageUrl"] = detail_data["additionalImages"][0]
                        product_data["variants"][0]["imageUrl"] = detail_data["additionalImages"][0]
                
                if detail_data["fullDescription"]:
                    # Update both the main description and the variant description
                    product_data["description"] = detail_data["fullDescription"]
                    
                # If we found color info, use it for the variant color
                if detail_data.get("colorInfo"):
                    product_data["variants"][0]["color"] = detail_data["colorInfo"]
                else:
                    product_data["variants"][0]["color"] = detail_data["fullDescription"]
                
                # Fetch detailed information about each variant
                complete_variants = [product_data["variants"][0]]  # Start with the current variant
                
                # Process other variants found on the detail page
                for variant in detail_data.get("variants", []):
                    if variant.get("sourceUrl") and variant.get("code") != variant_code:  # Skip current variant
                        variant_detail = await fetch_variant_details(context, variant.get("sourceUrl"), product_data)
                        if variant_detail:
                            complete_variants.append(variant_detail)
                
                # Replace the variants array with complete data
                product_data["variants"] = complete_variants

        return product_data
    except Exception as e:
        print(f"Error processing product from listing: {e}")
        return None
