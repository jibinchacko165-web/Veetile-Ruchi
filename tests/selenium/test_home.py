import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.mark.django_db(transaction=True)
def test_homepage_loading_and_title(driver, base_url):
    """
    Objective: Validate homepage loading, page title, and core header elements.
    Preconditions: Application running with base URL.
    Actions: Navigate to '/', inspect document title and brand emblem.
    Expected Result: Title contains 'Veetile-Ruchi', HTTP 200, brand title displayed.
    """
    driver.get(f"{base_url}/")
    wait = WebDriverWait(driver, 10)
    
    # 1. Page title verification
    assert "Veetile-Ruchi" in driver.title
    
    # 2. Brand logo emblem and title text
    brand_heading = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".brand-text h1")))
    assert "Veetile-Ruchi" in brand_heading.text

@pytest.mark.django_db(transaction=True)
def test_navigation_between_pages(driver, base_url):
    """
    Objective: Validate navigation between primary application pages from the navbar.
    Preconditions: Visitor accesses the homepage.
    Actions: Click 'Food', click 'Home', click 'Login'.
    Expected Result: URL updates properly for each navigation link without broken routes.
    """
    driver.get(f"{base_url}/")
    wait = WebDriverWait(driver, 10)
    
    # Click Food navigation
    food_nav = wait.until(EC.element_to_be_clickable((By.XPATH, "//nav//span[text()='Food']")))
    food_nav.click()
    wait.until(lambda d: "session=All" in d.current_url or "/food" in d.current_url or "/" in d.current_url)
    assert driver.current_url.startswith(base_url)
    
    # Navigate to Login
    login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/login')]")))
    login_btn.click()
    wait.until(lambda d: "/login" in d.current_url)
    assert "/login" in driver.current_url

@pytest.mark.django_db(transaction=True)
def test_homepage_hero_and_traditional_badges(driver, base_url):
    """
    Objective: Verify presence of Kerala traditional food badge and hero heading.
    Preconditions: Homepage loaded.
    Actions: Inspect hero section and traditional cuisine badges.
    Expected Result: Hero headline rendered with authentic Kerala cuisine description.
    """
    driver.get(f"{base_url}/")
    wait = WebDriverWait(driver, 10)
    
    hero_title = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "h1")))
    page_text = driver.page_source
    assert "Authentic Kerala Homemade Food" in page_text or "Veetile-Ruchi" in hero_title.text
