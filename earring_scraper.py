from seleniumbase import Driver
import time
import json
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


driver = Driver(uc=True, headless=False)

base_url = (
    "https://www.neimanmarcus.com/c/jewelry-accessories-jewelry-earrings-cat4870732?"
    "priorityProdId=prod270260708&icid=VN_BROWSE_JW_JEWELRY_EARRINGS_2032026"
)

# ==============================
# PROGRESS TRACKING FILES
# ==============================
PROGRESS_FILE = "Earring_scraping_progress.json"
ERRORS_FILE = "Earring_scraping_errors.json"
RESULTS_FILE = "Earring_products.json"


def click_if_exists_and_refresh():
    """Handle 'Continue Shopping' modal if it appears."""
    try:
        button = driver.find_element(
            By.XPATH, "//button[.//label[text()='Continue Shopping']]"
        )
        if button.is_displayed():
            print("✅ Button found → clicking")
            # This is a modal dismiss; keeping JS click here is OK,
            # but you can convert it to .click() if it works reliably.
            driver.execute_script("arguments[0].click();", button)
            time.sleep(1)
            driver.back()
            time.sleep(1)
            driver.refresh()
            time.sleep(2)
        else:
            print("⏭️ Button not visible → skipping")
    except Exception:
        print("⏭️ Button not found → skipping")


def load_progress():
    """Load previously scraped products"""
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("scraped_urls", [])), data.get("current_page", 0)
    except Exception:
        return set(), 0


def load_results():
    """Load previously saved results"""
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def load_errors():
    """Load error log"""
    try:
        with open(ERRORS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_progress(scraped_urls, current_page):
    """Save progress for resume"""
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "scraped_urls": list(scraped_urls),
                "current_page": current_page,
                "timestamp": datetime.now().isoformat(),
            },
            f,
            indent=4,
        )


def save_results(results_):
    """Save results"""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results_, f, ensure_ascii=False, indent=4)


def save_error(url, error_msg):
    """Log error for manual review"""
    errors = load_errors()
    errors.append(
        {"url": url, "error": str(error_msg), "timestamp": datetime.now().isoformat()}
    )
    with open(ERRORS_FILE, "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=4)


# ==============================
# SCROLL TO LOAD ALL PRODUCTS
# ==============================
def scroll_and_load_all_products():
    """Scroll down to trigger lazy loading of all products on the page"""
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            break
        last_height = new_height


# ==============================
# GET PRODUCT URLS
# ==============================
def get_product_urls():
    """Get all product URLs from the current page"""
    products = driver.find_elements("css selector", "a.product-thumbnail__link[href]")
    urls = []
    for p in products:
        url = p.get_attribute("href")
        if url:
            urls.append(url)
    return urls


# ==============================
# SAFE GET TEXT
# ==============================
def get_text(xpath_list):
    if isinstance(xpath_list, str):
        xpath_list = [xpath_list]

    for xp in xpath_list:
        try:
            el = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            text = el.text.strip()
            if text:
                return text
        except Exception:
            continue

    return ""


# ==============================
# CLICK SEE MORE
# ==============================
def click_see_more():
    try:
        btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, "//p[normalize-space()='See More']"))
        )
        # Here too: using normal click
        btn.click()
        time.sleep(1)
    except Exception:
        pass


# ==============================
# CLICK NEXT (SCROLL THEN DRIVER CLICK)
# ==============================
def click_next_page():
    """
    Scroll to the Next button, then click using WebDriver click (NOT JS click).
    Returns True if clicked, False if Next is not found/clickable.
    """
    next_xpath = '(//a[@aria-label="Next"])[2]'

    try:
        # Present in DOM
        next_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, next_xpath))
        )

        # Scroll into view
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
            next_button,
        )
        time.sleep(2)

        # Clickable
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, next_xpath))
        )

        # Native click (no JS)
        try:
            next_button.click()
        except Exception:
            # Still not JS: ActionChains click
            ActionChains(driver).move_to_element(next_button).pause(0.2).click().perform()

        # Wait for product tiles to exist again (new page)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.product-thumbnail__link"))
        )

        return True

    except Exception as e:
        print(f"❌ No more pages or Next click failed: {e}")
        return False


# ==============================
# SCRAPE A SINGLE PRODUCT PAGE
# ==============================
def scrape_product(url, page_index, product_urls):
    main_window = driver.current_window_handle

    try:
        driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(2)

        driver.switch_to.window(driver.window_handles[-1])
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception as e:
        print(f"❌ Navigation error at index {page_index}: {e}")
        save_error(url, f"Navigation error: {e}")
        try:
            driver.close()
            driver.switch_to.window(main_window)
        except Exception:
            pass
        return None

    try:
        # Initialize variables to empty strings to avoid UnboundLocalError
        brand = ""
        product_name = ""
        price = ""

        click_see_more()

        if not brand:
            brand = get_text(
                [
                    "//a[@data-test='pdp-designer']",
                    "//span[@class='brand']",
                    "//a[contains(@href,'designer')]",
                    "//span[contains(@class,'product-title__brand')]",
                ]
            )

        if not product_name:
            product_name = get_text(
                [
                    '//*[@id="buy-block-container"]/div[2]/h1/span',
                    "//span[contains(@class,'product-title__name')]",
                    "//h1",
                ]
            )

        category = get_text(
            [
                '//*[@id="buy-block-container"]/div[1]/nav/ul/li[1]/a',
                "//nav[contains(@class,'breadcrumb')]//a[1]",
                "//ol[contains(@class,'breadcrumb')]//a[1]",
            ]
        )

        sub_category = get_text(
            [
                "//li[@aria-current='page']//a",
                "//nav[contains(@class,'breadcrumb')]//a[last()]",
                "//ol[contains(@class,'breadcrumb')]//a[last()]",
            ]
        )

        # Set defaults if empty
        if not category:
            category = "Jewelry"
        if not sub_category:
            sub_category = "Earrings"

        if not price:
            price = get_text(
                [
                    '//*[@id="buy-block-container"]/div[3]/div[1]/span',
                    "//span[contains(@class,'product-pricing__price')]",
                ]
            )

        category = "Jewelry"
        sub_category = "Earrings"

        product_details = get_text("/html/body/div[5]/div[3]/div/div/div[1]/ul")
        description = get_text("/html/body/div[5]/div[3]/div/div/div[3]")

        materials = get_text(
            "(//ul/li[contains(.,'karat') or contains(.,'brass') or contains(.,'silver ')])[2]"
        )
        measurements = get_text("(//ul/li[contains(.,'Approx.') or contains(.,'initial')])[2]")

        weight = get_text("(//ul/li[contains(.,'carat')])[2]") or get_text(
            "(//ul/li[contains(.,'weight')])[3]"
        )

        country = get_text("((//ul/li[contains(.,'Made in') or contains(.,'Imported')])[2])")
        stone_type = get_text("/html/body/div[5]/div[3]/div/div/div[1]/ul/li[3]")
        embellishment = get_text("/html/body/div[5]/div[3]/div/div/div[1]/ul/li[4]")
        season = get_text("//li[contains(.,'Season')]")

        # ==============================
        # SKU (JSON-LD)
        # ==============================
        sku = ""
        try:
            script_elements = driver.find_elements(By.XPATH, "//script[@data-testid='schema']")
            for script_elem in script_elements:
                try:
                    json_ld = json.loads(script_elem.get_attribute("innerHTML"))
                    if json_ld.get("hasVariant") and len(json_ld["hasVariant"]) > 0:
                        variant = json_ld["hasVariant"][0]
                        if isinstance(variant, list) and len(variant) > 0:
                            sku = variant[0].get("sku", "")
                        else:
                            sku = variant.get("sku", "")

                        if sku:
                            print(f"Extracted SKU at index {page_index}: {sku}")
                            break
                except Exception:
                    continue
        except Exception as e:
            print(f"SKU extraction error at index {page_index}: {e}")

        # ==============================
        # COLORS
        # ==============================
        colors = []
        try:
            # Get from the label span
            color_elements = driver.find_elements(
                By.XPATH, "//p[contains(., 'Color')]//span"
            )
            for c in color_elements:
                text = c.text.strip()
                if text and text not in colors:
                    colors.append(text)

            # Get from swatch alt texts
            swatch_imgs = driver.find_elements(
                By.XPATH, "//ul[@data-test='pdp-color-swatches']//img"
            )
            for img in swatch_imgs:
                alt = img.get_attribute("alt")
                if alt and alt not in colors:
                    colors.append(alt)

        except Exception as e:
            print("Color error:", e)

        # ==============================
        # IMAGES
        # ==============================
        image_urls = []
        try:
            images = driver.find_elements(By.XPATH, "//img")
            for img in images:
                src = img.get_attribute("data-src") or img.get_attribute("src")
                if src and src.startswith("http") and src not in image_urls:
                    image_urls.append(src)
        except Exception:
            pass

        max_images = 5
        image_urls = image_urls[:max_images] + [""] * (max_images - len(image_urls))

        data = {
            "Brand": brand,
            "Product Name": product_name,
            "Category": category,
            "Sub-category": sub_category,
            "Price USD": price,
            "Available colours": ", ".join(colors),
            "SKU / Style code": sku,
            "Product Details": product_details,
            "Description": description,
            "Materials": materials,
            "Measurements": measurements,
            "Weight": weight,
            "Stone type": stone_type,
            "Country of origin": country,
            "Metal type / leather type": materials,
            "Embellishment": embellishment,
            "Season": season,
            "Product URL": url,
            "Image1 URL": image_urls[0],
            "Image2 URL": image_urls[1],
            "Image3 URL": image_urls[2],
            "Image4 URL": image_urls[3],
            "Image5 URL": image_urls[4],
            "Scrape date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        print(f"✅ Scraped {page_index + 1}/{len(product_urls)}")
        return data

    except Exception as e:
        print(f"❌ Error scraping product {url}: {e}")
        save_error(url, f"Scraping error: {e}")
        return None

    finally:
        try:
            driver.close()
            driver.switch_to.window(main_window)
        except Exception:
            pass


# ==============================
# MAIN
# ==============================
scraped_urls, current_page = load_progress()
results = load_results()

print(f"📋 Resuming from page {current_page}")
print(f"✅ Already scraped: {len(scraped_urls)} products")
print(f"📊 Total results so far: {len(results)}\n")

# Navigate to the starting page
page_url = base_url + f"&page={current_page}"
driver.get(page_url)
click_if_exists_and_refresh()

# --- Scrape the starting page
print("🔄 Scrolling to load all products...")
scroll_and_load_all_products()
print("✅ All products loaded")

product_urls = get_product_urls()
print(f"🔗 Products found: {len(product_urls)}")

for page_index, url in enumerate(product_urls):
    if url in scraped_urls:
        print(f"⏭️ Skipping already scraped product: {url}")
        continue

    data = scrape_product(url, page_index, product_urls)
    if not data:
        continue

    results.append(data)
    scraped_urls.add(url)

    save_results(results)
    save_progress(scraped_urls, current_page)
    print("✅ Progress saved")

# --- Pagination loop
while True:
    print("\n" + "=" * 50)
    print(f"📄 Current page: {current_page}")
    print("=" * 50)

    clicked = click_next_page()
    if not clicked:
        break

    current_page += 1
    save_progress(scraped_urls, current_page)
    print(f"➡️ Moved to page {current_page}")

    scroll_and_load_all_products()
    product_urls = get_product_urls()
    print(f"🔗 Products found: {len(product_urls)}")

    for page_index, url in enumerate(product_urls):
        if url in scraped_urls:
            continue

        data = scrape_product(url, page_index, product_urls)
        if not data:
            continue

        results.append(data)
        scraped_urls.add(url)

        save_results(results)
        save_progress(scraped_urls, current_page)
        print("✅ Progress saved")

print("\n" + "=" * 50)
print("🎉 Scraping completed!")
print(f"Total products scraped: {len(results)}")
print("=" * 50)

# Optional: driver.quit()
