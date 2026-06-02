#!/usr/bin/env python3
"""jarvis_browser.py — browser automation avanzata con Playwright + AppleScript v2.0"""
import subprocess, json, os, time
from pathlib import Path

BROWSER_STATE_FILE = Path(__file__).parent / "data" / "browser_state.json"

def _ensure_data_dir():
    BROWSER_STATE_FILE.parent.mkdir(exist_ok=True)

def _run(cmd, timeout=15):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()

def open_url(url, browser="default"):
    if not url.startswith("http"):
        url = "https://" + url
    aliases = {"chrome": "Google Chrome", "firefox": "Firefox", "safari": "Safari", "arc": "Arc", "edge": "Microsoft Edge"}
    browser_name = aliases.get(browser.lower(), browser) if browser != "default" else ""
    if browser_name:
        rc, _ = _run(f'open -a "{browser_name}" "{url}"')
    else:
        rc, _ = _run(f'open "{url}"')
    return f"✅ Aperto: {url}" if rc == 0 else f"⚠ Impossibile aprire {url}"

def search_web(query, browser="default"):
    import urllib.parse
    q = urllib.parse.quote_plus(query)
    return open_url(f"https://www.google.com/search?q={q}", browser)

def get_page_content_js():
    script = '''
    tell application "Google Chrome"
        if (count of windows) > 0 then
            set activeTab to active tab of window 1
            set pageTitle to title of activeTab
            set pageURL to URL of activeTab
            return pageTitle & "|" & pageURL
        else
            return "NO_TAB"
        end if
    end tell
    '''
    rc, result = _run(f"osascript -e '{script}'")
    if result and result != "NO_TAB":
        parts = result.split("|")
        return {"title": parts[0], "url": parts[1] if len(parts) > 1 else ""}
    return {"title": "Nessuna pagina attiva", "url": ""}

def get_browser_tabs():
    script = '''
    set tabList to ""
    tell application "Google Chrome"
        if (count of windows) > 0 then
            repeat with t in (tabs of window 1)
                set tabList to tabList & (title of t) & "|" & (URL of t) & "\\n"
            end repeat
        end if
    end tell
    return tabList
    '''
    rc, result = _run(f"osascript -e '{script}'")
    if not result:
        return "Nessun tab aperto"
    tabs = []
    for line in result.strip().split("\n"):
        if "|" in line:
            parts = line.split("|")
            tabs.append({"title": parts[0], "url": parts[1]})
    return tabs if tabs else "Nessun tab aperto"

def click_element(selector=""):
    if not selector:
        return "⚠ Selettore mancante"
    script = f'''
    tell application "Google Chrome"
        set activeTab to active tab of window 1
        execute activeTab javascript "document.querySelector('{selector}').click();"
    end tell
    '''
    rc, _ = _run(f"osascript -e '{script}'")
    return f"✅ Cliccato: {selector}" if rc == 0 else f"⚠ Impossibile cliccare {selector}"

def fill_form(selector, text):
    script = f'''
    tell application "Google Chrome"
        set activeTab to active tab of window 1
        execute activeTab javascript "var el=document.querySelector('{selector}'); el.value='{text}'; el.dispatchEvent(new Event('input',{{bubbles:true}}));"
    end tell
    '''
    rc, _ = _run(f"osascript -e '{script}'")
    return f"✅ Compilato: {selector}" if rc == 0 else f"⚠ Impossibile compilare {selector}"

def scroll_page(direction="down"):
    directions = {
        "down": "window.scrollBy(0,500)",
        "up": "window.scrollBy(0,-500)",
        "top": "window.scrollTo(0,0)",
        "bottom": "window.scrollTo(0,document.body.scrollHeight)"
    }
    js = directions.get(direction, directions["down"])
    script = f'''
    tell application "Google Chrome"
        set activeTab to active tab of window 1
        execute activeTab javascript "{js}"
    end tell
    '''
    rc, _ = _run(f"osascript -e '{script}'")
    return f"✅ Scroll {direction}" if rc == 0 else f"⚠ Scroll fallito"

# ── PLAYWRIGHT AUTOMATION AVANZATA ──

def playwright_navigate(url, headless=False):
    """Naviga a URL con Playwright e ritorna contenuto pagina"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "⚠ Playwright non installato: pip install playwright && playwright install chromium"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            title = page.title()
            url_final = page.url
            content = page.inner_text("body")[:2000]
            
            browser.close()
            return {
                "status": "ok",
                "title": title,
                "url": url_final,
                "content": content[:500] + "..." if len(content) > 500 else content
            }
    except Exception as e:
        return f"⚠ Errore Playwright: {e}"

def playwright_click(selector, url=None):
    """Clicca elemento con Playwright"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "⚠ Playwright non installato"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            if url:
                page.goto(url, wait_until="domcontentloaded", timeout=10000)
            page.click(selector, timeout=5000)
            page.wait_for_timeout(1000)
            
            result = {
                "status": "ok",
                "url": page.url,
                "title": page.title()
            }
            browser.close()
            return result
    except Exception as e:
        return f"⚠ Errore click: {e}"

def playwright_fill(selector, text, url=None):
    """Compila campo form con Playwright"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "⚠ Playwright non installato"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            if url:
                page.goto(url, wait_until="domcontentloaded", timeout=10000)
            page.fill(selector, text, timeout=5000)
            page.wait_for_timeout(500)
            
            result = {"status": "ok", "filled": selector}
            browser.close()
            return result
    except Exception as e:
        return f"⚠ Errore fill: {e}"

def playwright_extract(url, selector="body"):
    """Estrae contenuto da pagina con Playwright"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "⚠ Playwright non installato"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            content = page.inner_text(selector)
            browser.close()
            return {
                "status": "ok",
                "title": page.title(),
                "content": content[:3000] + "..." if len(content) > 3000 else content
            }
    except Exception as e:
        return f"⚠ Errore extract: {e}"

def playwright_screenshot(url, save_path=None):
    """Screenshot pagina con Playwright"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "⚠ Playwright non installato"
    
    p = save_path or os.path.expanduser("~/Desktop/jarvis_page.png")
    
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.screenshot(path=p, full_page=True)
            browser.close()
            return {"status": "ok", "path": p}
    except Exception as e:
        return f"⚠ Errore screenshot: {e}"

def install_playwright():
    rc, _ = _run("pip install playwright")
    if rc == 0:
        _run("playwright install chromium")
        return "✅ Playwright installato"
    return "⚠ Installazione Playwright fallita"
