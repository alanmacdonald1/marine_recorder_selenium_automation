"""
IMPORTANT — DATA DELETION WARNING
--------------------------------
This script will PERMANENTLY DELETE DATA from your
Marine Recorder Management database.

If you are unsure, DO NOT RUN this script.
Alternatively, remove or disable the `delete_replicate` function
before execution.

Overview
--------
This script automates the deletion of replicate projects from the
Marine Recorder Management web application using Selenium.

Requirements
------------
Install required dependencies before running:

    pip install selenium webdriver-manager

Configuration
-------------
Update the following variables as needed:

- BASE_URL:
    URL of the Marine Recorder Management site.

- PAGES_TO_PROCESS:
    Number of replicate pages to process.

Customization
-------------
To target different entities (e.g. `surveyevent` instead of `replicate`):

- Edit the `click_replicate_from_welcome` function.
- Update the `href` value to point to the relevant page.

Use with caution.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select

BASE_URL = "https://management.marine-recorder.org.uk/"
PAGES_TO_PROCESS = 100


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

from selenium.common.exceptions import ElementClickInterceptedException

def wait_for_kendo_not_loading(driver, timeout=30):
    wait = WebDriverWait(driver, timeout)

    def no_overlay(d):
        try:
            overlays = d.find_elements(By.CSS_SELECTOR, ".k-loading-mask, .k-loading-image")
            return all(not o.is_displayed() for o in overlays)
        except StaleElementReferenceException:
            return False

    wait.until(no_overlay)

def wait_for_user_login(driver, timeout=600):
    wait = WebDriverWait(driver, timeout)
    print("Chrome opened. Please login manually...")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#welcome-tile-layout")))
    print("Welcome page detected.")


def click_replicate_from_welcome(driver, timeout=30):
    wait = WebDriverWait(driver, timeout)
    link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/ProjectSetup/Replicate']")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
    link.click()


def wait_for_replicate_grid_present(driver, timeout=60):
    wait = WebDriverWait(driver, timeout)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#rep-grid")))
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#rep-grid .k-grid-table")))
    return wait


def wait_for_grid_data_bound(driver, timeout=60):
    """
    Wait until the grid has either:
      - at least 1 data row, OR
      - a 'no records' element/message
    so we don't read 0 rows prematurely.
    """
    wait = WebDriverWait(driver, timeout)

    def _grid_ready(d):
        rows = d.find_elements(By.CSS_SELECTOR, "#rep-grid tbody tr.k-master-row")
        if len(rows) > 0:
            return True
        # Kendo can show "no records" in different ways; check a couple
        no1 = d.find_elements(By.CSS_SELECTOR, "#rep-grid .k-grid-norecords")
        no2 = d.find_elements(By.CSS_SELECTOR, "#rep-grid .k-no-data, #rep-grid .k-grid-norecords-template")
        return len(no1) > 0 or len(no2) > 0

    wait.until(_grid_ready)


def rows_on_page(driver):
    return driver.find_elements(By.CSS_SELECTOR, "#rep-grid tbody tr.k-master-row")


def get_current_page(driver) -> int:
    # Kendo pager dropdown exists in your HTML
    sel = Select(driver.find_element(By.CSS_SELECTOR, "#rep-grid .k-pager select"))
    return int(sel.first_selected_option.get_attribute("value"))

def go_to_page(driver, page_num: int, timeout=30) -> bool:
    """
    Selects a page from the pager dropdown.
    Returns False if the page option isn't present (e.g., you deleted so much pages collapsed).
    """
    wait_for_kendo_not_loading(driver, timeout=timeout)

    sel_el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#rep-grid .k-pager select"))
    )
    sel = Select(sel_el)

    values = [o.get_attribute("value") for o in sel.options]
    if str(page_num) not in values:
        return False

    sel.select_by_value(str(page_num))

    # wait for grid refresh
    wait_for_grid_data_bound(driver, timeout=timeout)
    wait_for_kendo_not_loading(driver, timeout=timeout)
    return True

def click_edit_for_row(driver, row_index):
    wait_for_kendo_not_loading(driver, timeout=30)

    # re-locate rows fresh (avoid stale)
    rows = rows_on_page(driver)
    edit = rows[row_index].find_element(By.CSS_SELECTOR, "a.k-grid-Edit")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", edit)

    # Wait until this specific element is clickable (lambda is reliable)
    WebDriverWait(driver, 20).until(lambda d: edit.is_displayed() and edit.is_enabled())

    try:
        edit.click()
    except ElementClickInterceptedException:
        wait_for_kendo_not_loading(driver, timeout=30)
        driver.execute_script("arguments[0].click();", edit)


def delete_replicate(driver):
    # Click Delete on the edit page
    wait_for_kendo_not_loading(driver, timeout=30)
    delete_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button#dialog-button"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", delete_btn)
    delete_btn.click()

    # Wait for the dialog and click "Yes"
    yes_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//div[contains(@class,'k-window') and contains(@class,'k-dialog')]"
            "//div[contains(@class,'k-dialog-actions')]"
            "//button[normalize-space()='Yes']"
        ))
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", yes_btn)
    yes_btn.click()

    # Wait until dialog goes away (prevents click interception)
    WebDriverWait(driver, 30).until(
        EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.k-window.k-dialog"))
    )

    # Back on grid page / refreshed
    wait_for_kendo_not_loading(driver, timeout=30)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#rep-grid")))


def next_page(driver, timeout=30) -> bool:
    # Wait until the "Next page" button exists
    btn_sel = "#rep-grid .k-pager button[aria-label='Go to the next page'], #rep-grid .k-pager button[title='Go to the next page']"
    wait = WebDriverWait(driver, timeout)

    def _enabled(d):
        try:
            b = d.find_element(By.CSS_SELECTOR, btn_sel)
            cls = b.get_attribute("class") or ""
            return "k-disabled" not in cls and b.is_displayed()
        except Exception:
            return False

    # If it never becomes enabled, we are at last page (or paging collapsed after deletions)
    try:
        wait.until(_enabled)
    except TimeoutException:
        return False

    btn = driver.find_element(By.CSS_SELECTOR, btn_sel)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    driver.execute_script("arguments[0].click();", btn)

    # wait for refresh
    wait_for_grid_data_bound(driver, timeout=timeout)
    wait_for_kendo_not_loading(driver, timeout=timeout)
    return True


def main():
    driver = make_driver()
    try:
        driver.get(BASE_URL)

        wait_for_user_login(driver, timeout=600)
        click_replicate_from_welcome(driver)

        wait_for_replicate_grid_present(driver)
        wait_for_grid_data_bound(driver)
        print("Replicate grid detected - starting automation.")


        for step in range(PAGES_TO_PROCESS):
            wait_for_replicate_grid_present(driver)
            wait_for_grid_data_bound(driver)
            wait_for_kendo_not_loading(driver, timeout=30)

            count = len(rows_on_page(driver))
            print(f"=== Processing page {step + 1} | Rows found: {count} ===")
            if count == 0:
                break

            deletions_this_page = 0
            while deletions_this_page < 10:
                wait_for_replicate_grid_present(driver)
                wait_for_grid_data_bound(driver)
                wait_for_kendo_not_loading(driver, timeout=30)

                rows = rows_on_page(driver)
                if not rows:
                    break

                click_edit_for_row(driver, 0)
                delete_replicate(driver)
                deletions_this_page += 1

            # move next (unless last iteration)
            if step < PAGES_TO_PROCESS - 1:
                if not next_page(driver):
                    print("No next page available (maybe last page after deletions). Stopping.")
                    break

        print("Done.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
