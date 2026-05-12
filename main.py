=============================== installation chrome ===============================


# 1. Добавляем ключи и репозиторий Google
!wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
!echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list

# 2. Установка Chrome
!apt-get update
!apt-get install -y google-chrome-stable

# 3. Установка менеджера драйверов
!pip install webdriver-manager selenium

  
===============================  launch chrome ===============================

  
  from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

try:
    # Менеджер сам скачает нужный драйвер и запустит его
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.get("https://www.google.com")
    print(f"ПОБЕДА! Браузер запущен. Титул: {driver.title}")
    driver.quit()
except Exception as e:
    print(f"Даже официальный Chrome выдал ошибку: {e}")


===============================  The Data Parser  ===============================


import time
import pandas as pd
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

def get_driver():
   options = Options()
   options.add_argument("--headless")
   options.add_argument("--no-sandbox")
   options.add_argument("--disable-dev-shm-usage")
   options.add_argument("--disable-gpu")
   options.add_argument("--window-size=1920,1080")
   options.add_argument("--disable-blink-features=AutomationControlled")
   options.add_experimental_option("excludeSwitches", ["enable-automation"])
   options.add_experimental_option("useAutomationExtension", False)
   options.binary_location = "/usr/bin/google-chrome-stable"

   service = Service(ChromeDriverManager().install())
   driver = webdriver.Chrome(service=service, options=options)
   driver.execute_cdp_cmd(
       "Page.addScriptToEvaluateOnNewDocument",
       {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
   )
   return driver


def fill_date_field(driver, field_id, date_str):
   """
   Robust date filler: clears via JS, sets value via JS,
   then fires change/input events so ASP.NET validators accept it.
   Avoids triggering the calendar popup.
   """
   script = f"""
       var el = document.getElementById('{field_id}');
       if (!el) {{
           // Fallback: find by placeholder or name
           el = document.querySelector('input[placeholder="MM/DD/YYYY"]');
       }}
       el.removeAttribute('readonly');
       el.value = '{date_str}';
       ['input', 'change', 'blur'].forEach(function(evt) {{
           el.dispatchEvent(new Event(evt, {{ bubbles: true }}));
       }});
       return el.id;
   """
   return driver.execute_script(script)


def click_search_button(driver):
   """
   Multi-strategy SEARCH button clicker.
   Tries standard selectors first, then JS text-matching loop as fallback.
   """
   strategies = [
       # Strategy 1: input[type=submit] with value SEARCH
       lambda d: d.find_element(By.CSS_SELECTOR, "input[type='submit'][value='SEARCH']"),
       # Strategy 2: input by value (case-insensitive via XPath)
       lambda d: d.find_element(By.XPATH, "//input[@value='SEARCH' or @value='Search']"),
       # Strategy 3: button tag with SEARCH text
       lambda d: d.find_element(By.XPATH, "//button[normalize-space(text())='SEARCH']"),
       # Strategy 4: any clickable element containing SEARCH text
       lambda d: d.find_element(By.XPATH, "//*[normalize-space(text())='SEARCH' and (self::input or self::button or self::a)]"),
   ]

   for i, strategy in enumerate(strategies):
       try:
           btn = strategy(driver)
           driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
           time.sleep(0.3)
           driver.execute_script("arguments[0].click();", btn)
           print(f"  ✓ Search button clicked via strategy {i+1}")
           return True
       except Exception:
           continue

   # Strategy 5: JS loop over all inputs/buttons matching text
   print("  ⚠ Standard strategies failed — trying JS text-loop fallback...")
   result = driver.execute_script("""
       var all = Array.from(document.querySelectorAll('input, button, a'));
       for (var el of all) {
           var txt = (el.value || el.innerText || '').trim().toUpperCase();
           if (txt === 'SEARCH') {
               el.click();
               return 'clicked:' + el.tagName + '#' + el.id;
           }
       }
       return null;
   """)

   if result:
       print(f"  ✓ JS fallback clicked: {result}")
       return True

   raise RuntimeError("SEARCH button not found by any strategy. Check debug screenshot.")


def wait_for_results(driver, timeout=30):
   """
   Waits for a results table or 'no records' message to appear.
   Returns True if results found, False if no records.
   """
   wait = WebDriverWait(driver, timeout)
   try:
       # Wait until either a results table or a 'no records' indicator appears
       wait.until(lambda d: (
           d.find_elements(By.CSS_SELECTOR, "table.rgMasterTable, table[id*='Grid'], table[class*='grid'], #gvResults") or
           d.find_elements(By.XPATH, "//*[contains(text(),'No records') or contains(text(),'no records') or contains(text(),'0 records')]") or
           len(d.find_elements(By.CSS_SELECTOR, "tr[class*='rgRow'], tr[class*='GridRow'], tr.odd, tr.even")) > 0
       ))

       no_records = driver.find_elements(
           By.XPATH,
           "//*[contains(text(),'No records') or contains(text(),'no records')]"
       )
       if no_records:
           print("  ℹ No records found for this date range.")
           return False
       return True

   except Exception:
       print("  ⚠ Timed out waiting for results table.")
       return False


def extract_results(driver):
   """
   Extracts results table into a DataFrame.
   Tries pd.read_html first, then manual tr/td iteration as fallback.
   """
   # Strategy 1: pd.read_html
   try:
       tables = pd.read_html(driver.page_source, flavor="lxml")
       # Pick the largest table (most likely to be results)
       if tables:
           df = max(tables, key=lambda t: len(t))
           if len(df) > 0:
               print(f"  ✓ Extracted {len(df)} rows via pd.read_html")
               return df
   except Exception as e:
       print(f"  ⚠ pd.read_html failed: {e} — trying manual extraction...")

   # Strategy 2: Manual tr/td extraction
   try:
       rows = driver.find_elements(
           By.CSS_SELECTOR,
           "table tr"
       )
       data = []
       for row in rows:
           cells = row.find_elements(By.CSS_SELECTOR, "td, th")
           data.append([c.text.strip() for c in cells])

       if data:
           df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame(data)
           # Drop completely empty rows
           df = df[df.apply(lambda r: r.astype(str).str.strip().ne('').any(), axis=1)]
           print(f"  ✓ Extracted {len(df)} rows via manual tr/td")
           return df
   except Exception as e:
       print(f"  ⚠ Manual extraction failed: {e}")

   return pd.DataFrame()  # Empty fallback


def scrape_harris(days_back=30, max_pages=10):
   """
   Scrapes Harris County Real Property records for the last `days_back` days.

   Args:
       days_back (int): Number of days to look back from today.
       max_pages (int): Max result pages to scrape (set None for unlimited).

   Returns:
       pd.DataFrame: Combined results across all pages.
   """
   URL = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"

   date_to   = datetime.today()
   date_from = date_to - timedelta(days=days_back)
   date_from_str = date_from.strftime("%m/%d/%Y")
   date_to_str   = date_to.strftime("%m/%d/%Y")

   print(f"📅 Scraping date range: {date_from_str} → {date_to_str}")

   driver = get_driver()
   wait   = WebDriverWait(driver, 20)
   all_dfs = []

   try:
       # ── 1. Navigate ───────────────────────────────────────────────────────
       print(f"\n🌐 Navigating to {URL}...")
       driver.get(URL)
       wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
       time.sleep(1.5)  # Let ASP.NET ViewState settle
       driver.save_screenshot("debug_01_page_loaded.png")
       print("  ✓ Page loaded")

       # ── 2. Fill Date (From) ───────────────────────────────────────────────
       print(f"\n📝 Filling Date (From): {date_from_str}")
       # Try known ASP.NET control IDs first, then fall back to placeholder query
       date_from_candidates = [
           "ctl00_cphMain_txtDateFrom",
           "txtDateFrom",
           "DateFrom",
       ]
       filled_from = False
       for field_id in date_from_candidates:
           try:
               el = driver.find_element(By.ID, field_id)
               fill_date_field(driver, field_id, date_from_str)
               filled_from = True
               print(f"  ✓ Filled via ID: {field_id}")
               break
           except Exception:
               continue

       if not filled_from:
           # Fallback: find by placeholder attribute
           els = driver.find_elements(By.CSS_SELECTOR, "input[placeholder='MM/DD/YYYY']")
           if els:
               driver.execute_script(f"arguments[0].value='{date_from_str}';", els[0])
               driver.execute_script(
                   "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", els[0]
               )
               print("  ✓ Date (From) filled via placeholder selector")

       # ── 3. Fill Date (To) ─────────────────────────────────────────────────
       print(f"\n📝 Filling Date (To): {date_to_str}")
       date_to_candidates = [
           "ctl00_cphMain_txtDateTo",
           "txtDateTo",
           "DateTo",
       ]
       filled_to = False
       for field_id in date_to_candidates:
           try:
               el = driver.find_element(By.ID, field_id)
               fill_date_field(driver, field_id, date_to_str)
               filled_to = True
               print(f"  ✓ Filled via ID: {field_id}")
               break
           except Exception:
               continue

       if not filled_to:
           els = driver.find_elements(By.CSS_SELECTOR, "input[placeholder='MM/DD/YYYY']")
           if len(els) >= 2:
               driver.execute_script(f"arguments[0].value='{date_to_str}';", els[1])
               driver.execute_script(
                   "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", els[1]
               )
               print("  ✓ Date (To) filled via placeholder selector")

       driver.save_screenshot("debug_02_dates_filled.png")

       # ── 4. Click SEARCH ───────────────────────────────────────────────────
       print("\n🔍 Clicking SEARCH button...")
       click_search_button(driver)
       time.sleep(2)
       driver.save_screenshot("debug_after_click.png")
       print("  ✓ Screenshot saved: debug_after_click.png")

       # ── 5. Wait for results ───────────────────────────────────────────────
       print("\n⏳ Waiting for results...")
       has_results = wait_for_results(driver)
       driver.save_screenshot("debug_03_results.png")

       if not has_results:
           print("  ℹ Returning empty DataFrame.")
           return pd.DataFrame()

       # ── 6. Extract + paginate ─────────────────────────────────────────────
       page = 1
       while True:
           print(f"\n📄 Extracting page {page}...")
           df = extract_results(driver)
           if not df.empty:
               df["_page"] = page
               all_dfs.append(df)

           if max_pages and page >= max_pages:
               print(f"  ℹ Reached max_pages={max_pages} limit.")
               break

           # Try to find a "Next page" link (Telerik RadGrid or standard pager)
           next_btn = driver.execute_script("""
               var candidates = Array.from(document.querySelectorAll('a, input[type=button]'));
               for (var el of candidates) {
                   var txt = (el.innerText || el.value || el.getAttribute('title') || '').trim();
                   if (txt === '>' || txt === 'Next' || txt.toLowerCase() === 'next page') {
                       return el;
                   }
               }
               return null;
           """)

           if not next_btn:
               print("  ✓ No more pages.")
               break

           driver.execute_script("arguments[0].click();", next_btn)
           time.sleep(2)
           wait_for_results(driver, timeout=20)
           page += 1

   except Exception as e:
       print(f"\n❌ Error: {e}")
       driver.save_screenshot("debug_error.png")
       raise

   finally:
       driver.quit()
       print("\n🔒 Driver closed.")

   # ── 7. Combine & return ───────────────────────────────────────────────────
   if all_dfs:
       combined = pd.concat(all_dfs, ignore_index=True)
       print(f"\n✅ Done! Total rows scraped: {len(combined)}")
       return combined

   print("\n⚠ No data extracted.")
   return pd.DataFrame()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
   df = scrape_harris(days_back=30, max_pages=5)

   if not df.empty:
       print("\n📊 Preview:")
       print(df.head(10).to_string(index=False))
       df.to_csv("harris_property_records.csv", index=False)
       print("\n💾 Saved to harris_property_records.csv")
   else:
       print("\n⚠ No records returned.")




===============================   The Lead Qualifier   ===============================



# ================================================================
#  Priority Filter v2 — вставь поверх предыдущей версии
#  Изменения: универсальный детектор бизнес-сущностей + метки причины
# ================================================================

import re
import pandas as pd

TOP_BUILDERS = [
    "LENNAR", "DR HORTON", "D.R. HORTON", "D R HORTON",
    "PULTE", "MERITAGE", "PERRY HOMES", "HIGHLAND HOMES",
    "TAYLOR MORRISON", "KB HOME", "KBHOME",
]

BUSINESS_SIGNALS = [
    (r"\bL\.L\.C\.?\b|\bLLC\b",              "[Corp: LLC]"),
    (r"\bL\.P\.?\b|\bLTD\b|\bLIMITED\b",     "[Corp: LTD/LP]"),
    (r"\bINC\.?\b|\bINCORPORATED\b",          "[Corp: INC]"),
    (r"\bCORP\.?\b|\bCORPORATION\b",          "[Corp: CORP]"),
    (r"\bPARTNERS\b|\bPARTNERSHIP\b",         "[Corp: Partners]"),
    (r"\bHOMES\b",                             "[New Construction]"),
    (r"\bBUILDERS?\b|\bBUILDING\b",           "[New Construction]"),
    (r"\bDEVELOPMENT\b|\bDEVELOPERS?\b",     "[Development]"),
    (r"\bREALTY\b|\bREAL\s+ESTATE\b",         "[Realty/RE]"),
    (r"\bINVESTMENT\b|\bINVESTMENTS\b",       "[Investment]"),
    (r"\bHOLDINGS?\b",                         "[Holdings]"),
    (r"\bPROPERTIES\b|\bPROPERTY\b",          "[Corp: Properties]"),
    (r"\bENTERPRISES?\b",                      "[Enterprise]"),
    (r"\bGROUP\b",                             "[Corp: Group]"),
    (r"\bBANK\b|\bBANKING\b",                 "[Bank/Finance]"),
    (r"\bMORTGAGE\b",                          "[Mortgage Co]"),
    (r"\bFINANCIAL\b|\bFINANCE\b",            "[Financial]"),
    (r"\bTRUST\b",                             "[Trust]"),
    (r"\bFUND\b|\bFUNDS\b",                   "[Fund]"),
]

_PERSON_PATTERN = re.compile(r"^[A-Z]+\s+[A-Z]+$")

def _looks_like_person(grantor):
    clean = grantor.strip().upper()
    if re.search(r"\b(LLC|INC|CORP|LTD|LP|L\.L\.C)\b", clean):
        return False
    return bool(_PERSON_PATTERN.match(clean))

def extract_grantor(names_str):
    m = re.search(r"Grantor:\s*(.+?)(?:Grantee:|Trustee:|$)", names_str, re.IGNORECASE)
    return m.group(1).strip() if m else names_str.strip()

def extract_grantee(names_str):
    m = re.search(r"Grantee:\s*(.+?)(?:Grantor:|Trustee:|$)", names_str, re.IGNORECASE)
    return m.group(1).strip() if m else ""

def detect_priority(grantor):
    upper = grantor.upper().strip()
    if _looks_like_person(upper):
        return False, ""
    for builder in TOP_BUILDERS:
        if re.search(re.escape(builder), upper, re.IGNORECASE):
            return True, "[Big Builder: {}]".format(builder.title())
    for pattern, label in BUSINESS_SIGNALS:
        if re.search(pattern, upper):
            return True, label
    return False, ""

def categorize_leads(df,
                     names_col="Names",
                     file_num_col="File Number",
                     date_col="File Date",
                     desc_col="Legal Description"):
    group_a = []
    group_b = []
    for _, row in df.iterrows():
        names    = str(row.get(names_col, ""))
        grantor  = extract_grantor(names)
        grantee  = extract_grantee(names)
        file_num = str(row.get(file_num_col, "")).strip()
        date     = str(row.get(date_col, "")).strip()
        address  = str(row.get(desc_col, "")).strip()
        is_priority, label = detect_priority(grantor)
        lead = {
            "file_number":    file_num,
            "date":           date,
            "grantee":        grantee or names,
            "grantor":        grantor,
            "address":        address,
            "priority_label": label,
        }
        (group_a if is_priority else group_b).append(lead)
    return {"priority": group_a, "standard": group_b}

def print_leads_report(results, max_standard=20):
    priority = results["priority"]
    standard = results["standard"]
    total    = len(priority) + len(standard)

    print("=" * 65)
    print("  HOUSTON SOLAR LEADS -- REPORT")
    print("  Total: {}  |  Priority: {}  |  Standard: {}".format(total, len(priority), len(standard)))
    print("=" * 65)

    print("\n[PRIORITY] GROUP A ({} leads)\n".format(len(priority)))
    print("   {:<4} {:<16} {:<12} {:<22} {:<28} {}".format(
        "#", "File #", "Date", "Reason", "Buyer", "Address"))
    print("   " + "-" * 110)
    for i, lead in enumerate(priority, 1):
        print("   {:<4}{:<16}{:<12}{:<22}{:<28}{}".format(
            i,
            lead["file_number"],
            lead["date"],
            lead["priority_label"],
            lead["grantee"][:26],
            lead["address"][:48],
        ))

    shown = min(len(standard), max_standard)
    print("\n[STANDARD] GROUP B ({} leads, showing {})\n".format(len(standard), shown))
    print("   {:<4} {:<16} {:<12} {:<32} {}".format("#", "File #", "Date", "Buyer", "Address"))
    print("   " + "-" * 100)
    for i, lead in enumerate(standard[:max_standard], 1):
        print("   {:<4}{:<16}{:<12}{:<32}{}".format(
            i,
            lead["file_number"],
            lead["date"],
            lead["grantee"][:30],
            lead["address"][:48],
        ))
    if len(standard) > max_standard:
        print("\n   ... and {} more leads".format(len(standard) - max_standard))

    if priority:
        print("\n" + "=" * 65)
        print("  EMAIL BLOCK -- copy and paste")
        print("=" * 65 + "\n")
        for lead in priority:
            print("* {}  |  {}  |  {}  |  {}".format(
                lead["grantee"], lead["priority_label"],
                lead["date"], lead["address"]))
    print("\n" + "=" * 65 + "\n")

def export_priority_csv(results, path="/content/priority_leads.csv"):
    if not results["priority"]:
        print("[-] No priority leads found")
        return
    df_out = pd.DataFrame(results["priority"])
    df_out.to_csv(path, index=False, encoding="utf-8-sig")
    print("[+] Priority CSV saved: {}  ({} rows)".format(path, len(df_out)))
    try:
        from google.colab import files
        files.download(path)
    except ImportError:
        pass

# ================================================================
#  CALL — run after df is ready
# ================================================================
results = categorize_leads(df)
print_leads_report(results, max_standard=20)
export_priority_csv(results)
