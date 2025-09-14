import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Load local environment variables from .env file (for local testing)
load_dotenv()

# Fetch credentials from environment variables
ROUTER_URL = os.getenv("ROUTER_URL", "https://192.168.0.1")
ROUTER_USERNAME = os.getenv("ROUTER_USERNAME", "admin")
ROUTER_PASSWORD = os.getenv("ROUTER_PASSWORD")

if not ROUTER_USERNAME or not ROUTER_PASSWORD:
    raise ValueError("Missing required environment variables: ROUTER_USERNAME and ROUTER_PASSWORD")

def reboot_router():
    driver = None  # ✅ Ensure driver is always initialized

    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in headless mode (removed to use real browser)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")  # Disable GPU
        options.add_argument("--user-data-dir=/tmp/chrome-user-data")  # Specify user data directory
        options.add_argument("--ignore-certificate-errors")  # Accept self-signed certificates
        # options.binary_location = "./chromedriver.linux"  # Specify the path to the Chrome binary
        driver = webdriver.Chrome(options=options)

        driver.get(ROUTER_URL)
        print(f"Navigated to {ROUTER_URL}")

        # Login
        print("Logging in...")
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, '//input[contains(@placeholder, "Username")]'))
        ).send_keys(ROUTER_USERNAME)
        print("Entered username")
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, '//input[contains(@placeholder, "Password")]'))
        ).send_keys(ROUTER_PASSWORD)
        print("Entered password")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type=submit]'))
        ).click()
        print("Clicked submit button")
        print("Waiting for page to load...")
        time.sleep(2)  # Wait for page load

        # Navigate to reboot section
        driver.get(ROUTER_URL + "/#/home/administration")
        print("Navigated to reboot page")
        time.sleep(2)  # Wait for page load

        # Click on the Reboot button
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Reboot")]'))
        ).click()
        time.sleep(2)  # Wait for page load
        print("Clicked on Reboot button")

        # Click on the confirmation button
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/section/section/div/div[1]/div/section/article/div/div/section[2]/div/table[1]/div/div/p/tbody/tr/th/div/button'))
        ).click()
        time.sleep(2)  # Wait for page load
        print("Clicked on confirmation button")

        # Click on the confirmation 2nd time
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/section/section/div/div[1]/div/section/article/div/div/section[2]/section/div/div/div[2]/div[2]/button[1]'))
        ).click()
        print("Clicked on confirmation button")

        print("✅ Router reboot initiated successfully.")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        if driver:  # ✅ Ensure driver.quit() is only called if driver was initialized
            driver.quit()
            print("Closed the browser")

if __name__ == "__main__":
    reboot_router()
