import json
import time
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

INPUT_FILE = "missing_price_urls.json"
OUTPUT_FILE = "collected_prices.json"


def save_results(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_text_safe(driver, xpath):
    try:
        return driver.find_element(By.XPATH, xpath).text.strip()
    except Exception:
        return ""


def click_see_more(driver):
    try:
        btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.XPATH, "//p[normalize-space()='See More']"))
        )
        btn.click()
        time.sleep(1)
    except Exception:
        pass


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = json.load(f)


driver = Driver(uc=True, headless=False)
results = []

try:
    for url in urls:
        try:
            driver.get(url)
            time.sleep(4)

            # Collect before click
            brand = get_text_safe(driver, '//*[@id="buy-block-container"]/div[2]/h1/a')
            product_name = get_text_safe(driver, '//*[@id="buy-block-container"]/div[2]/h1/span')
            price = get_text_safe(driver, '//*[@id="buy-block-container"]/div[3]/div/span')

            click_see_more(driver)

            # Collect after click
            product_details = get_text_safe(driver, "/html/body/div[5]/div[3]/div/div/div[1]/ul")
            description = get_text_safe(driver, "/html/body/div[5]/div[3]/div/div/div[3]")
            materials = get_text_safe(
                driver,
                "(//ul/li[contains(.,'karat') or contains(.,'brass') or contains(.,'silver ')])[2]",
            )
            measurements = get_text_safe(
                driver,
                "(//ul/li[contains(.,'Approx.') or contains(.,'initial')])[2]",
            )

            weight = get_text_safe(driver, "(//ul/li[contains(.,'carat')])[2]")
            if not weight:
                weight = get_text_safe(driver, "(//ul/li[contains(.,'weight')])[3]")

            country = get_text_safe(
                driver,
                "((//ul/li[contains(.,'Made in') or contains(.,'Imported')])[2])",
            )
            stone_type = get_text_safe(driver, "/html/body/div[5]/div[3]/div/div/div[1]/ul/li[3]")
            embellishment = get_text_safe(driver, "/html/body/div[5]/div[3]/div/div/div[1]/ul/li[4]")

            results.append(
                {
                    "Product URL": url,
                    "Brand": brand,
                    "Product Name": product_name,
                    "Price USD": price,
                    "Product Details": product_details,
                    "Description": description,
                    "Materials": materials,
                    "Measurements": measurements,
                    "Weight": weight,
                    "Stone type": stone_type,
                    "Country of origin": country,
                    "Metal type / leather type": materials,
                    "Embellishment": embellishment,
                }
            )

            save_results(results)
            print(f"✔ Done: {url}")

        except Exception as e:
            save_results(results)
            print(f"❌ Error: {url} {e}")
            continue
finally:
    driver.quit()

print("✅ All done!")
