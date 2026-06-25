"""
Reddit Teacher Review Scraper - SELENIUM VERSION (no API keys)
================================================================
Drives an actual Chrome browser using YOUR logged-in Reddit account/session
to search a subreddit for mentions of a teacher and gauge sentiment from
the comments. Uses old.reddit.com because its plain HTML is far more
reliable to scrape than new Reddit's shadow-DOM web components.

-----------------------------------------------------------------------
SETUP (one-time, ~2 minutes)
-----------------------------------------------------------------------
1. Install dependencies:
       pip install selenium nltk

2. Make sure you have Google Chrome installed (regular desktop Chrome).
   Selenium 4.10+ auto-downloads the matching chromedriver for you --
   no manual driver setup needed.

3. Run it:
       python reddit_teacher_scraper_selenium.py r/YourCollegeSubreddit "Professor Smith" "Smith"

4. A Chrome window will open. The FIRST time you run this:
   - It'll pause and ask you to log into Reddit manually in that window.
   - Once logged in, press Enter in your terminal to continue.
   - Your login is saved in a local browser profile folder (./chrome_profile)
     so you won't have to log in again on future runs.

-----------------------------------------------------------------------
IMPORTANT NOTES
-----------------------------------------------------------------------
- This is slower than the API version (it's loading real web pages) and
  more fragile (if Reddit changes old.reddit.com's HTML, selectors may
  need updating).
- Automated browsing is against Reddit's terms of service regardless of
  whether you use your own logged-in account or not. Keep request volume
  reasonable (this script already adds delays between page loads).
- Large comment threads only get partially expanded (controlled by
  MAX_LOAD_MORE_CLICKS below) to keep runtime reasonable -- increase it
  if you want more thoroughness at the cost of speed.
-----------------------------------------------------------------------
"""

import os
import sys
import csv
import time
import argparse
import re
from datetime import datetime
from collections import defaultdict
from urllib.parse import quote

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import NoSuchElementException, TimeoutException
except ImportError:
    sys.exit("Missing dependency. Run: pip install selenium nltk")

try:
    from nltk.sentiment import SentimentIntensityAnalyzer
    import nltk
    try:
        SentimentIntensityAnalyzer()
    except LookupError:
        nltk.download("vader_lexicon")
except ImportError:
    sys.exit("Missing dependency. Run: pip install selenium nltk")


# -----------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------
PROFILE_DIR = os.path.abspath("./chrome_profile")  # keeps you logged in between runs
MAX_SEARCH_PAGES = 3          # pages of search results to page through per name (~25 results/page)
MAX_LOAD_MORE_CLICKS = 5      # "load more comments" clicks per post (higher = more thorough, slower)
PAGE_LOAD_DELAY = 2           # seconds to wait after navigating, be polite / let JS settle
HEADLESS = False              # keep False so you can log in manually the first time


def setup_driver():
    options = Options()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    if HEADLESS:
        options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    return driver


def ensure_login(driver):
    driver.get("https://old.reddit.com")
    time.sleep(PAGE_LOAD_DELAY)
    try:
        driver.find_element(By.CSS_SELECTOR, "span.user a")
        print("Already logged in.")
        return
    except NoSuchElementException:
        pass

    print("\n" + "=" * 60)
    print("LOGIN REQUIRED")
    print("=" * 60)
    print("A Chrome window is open. Please log into your Reddit account")
    print("in that window now.")
    input("Once you're logged in, press Enter here to continue...")


def get_teacher_categories(text, names):
    categories = set()
    text_lower = text.lower()
    
    explicit_matches = set()
    for name in names:
        if name.lower() in text_lower:
            explicit_matches.add(name.strip().title())
            
    for name in names:
        base = name.lower()
        clean_name = name.replace("Professor ", "").replace("Prof. ", "").strip().title()
        
        # Trailing initial
        pattern = r'\b' + re.escape(base) + r'\s+([a-z])\b'
        for match in re.finditer(pattern, text_lower):
            categories.add(f"{clean_name} {match.group(1).upper()}")
            
        # Preceding initial
        pattern_pre = r'\b([a-z])\.?\s+' + re.escape(base) + r'\b'
        for match in re.finditer(pattern_pre, text_lower):
            initial = match.group(1)
            if initial in ['a', 'i'] and '.' not in match.group(0):
                continue
            categories.add(f"{clean_name} {initial.upper()}")

    if categories:
        return list(categories)
        
    if explicit_matches:
        best_match = sorted(list(explicit_matches), key=len, reverse=True)[0]
        if len(best_match.split()) == 1:
            return [f"{best_match} (Unspecified)"]
        else:
            return [best_match]
            
    return []


def collect_post_links(driver, subreddit, names):
    """Search old.reddit for posts matching any name variant, return a
    deduped list of post URLs."""
    links = set()
    for name in names:
        query = quote(f'"{name}"')
        for page in range(MAX_SEARCH_PAGES):
            if page == 0:
                url = f"https://old.reddit.com/r/{subreddit}/search?q={query}&restrict_sr=on&sort=new"
            else:
                # old.reddit pagination uses an "after" cursor; simplest robust
                # approach is to click "next" rather than build the URL by hand
                break
            driver.get(url)
            time.sleep(PAGE_LOAD_DELAY)

            anchors = driver.find_elements(By.CSS_SELECTOR, "a.search-title")
            if not anchors:
                # fallback selector in case Reddit's markup differs slightly
                anchors = [a for a in driver.find_elements(By.CSS_SELECTOR, "a")
                           if "/comments/" in (a.get_attribute("href") or "")]
            for a in anchors:
                href = a.get_attribute("href")
                if href:
                    links.add(href)

            # follow "next" pagination links for this query, up to MAX_SEARCH_PAGES
            for _ in range(MAX_SEARCH_PAGES - 1):
                try:
                    next_link = driver.find_element(By.CSS_SELECTOR, "a[rel='nofollow next']")
                    next_link.click()
                    time.sleep(PAGE_LOAD_DELAY)
                    anchors = driver.find_elements(By.CSS_SELECTOR, "a.search-title")
                    for a in anchors:
                        href = a.get_attribute("href")
                        if href:
                            links.add(href)
                except NoSuchElementException:
                    break
        print(f"  '{name}': {len(links)} unique posts found so far")

    return list(links)


def expand_comments(driver, max_clicks):
    clicks = 0
    while clicks < max_clicks:
        try:
            more_buttons = driver.find_elements(By.CSS_SELECTOR, "span.morecomments a")
            if not more_buttons:
                break
            more_buttons[0].click()
            clicks += 1
            time.sleep(1.5)
        except Exception:
            break


def scrape_post(driver, url, names):
    mentions = []
    full_url = url if "?" in url else url + "?limit=500"
    driver.get(full_url)
    time.sleep(PAGE_LOAD_DELAY)

    # --- post title + self-text ---
    try:
        title = driver.find_element(By.CSS_SELECTOR, "a.title").text
    except NoSuchElementException:
        title = ""
    try:
        selftext = driver.find_element(By.CSS_SELECTOR, "div.expando div.usertext-body div.md").text
    except NoSuchElementException:
        selftext = ""

    post_text = f"{title} {selftext}".strip()
    if post_text:
        categories = get_teacher_categories(post_text, names)
        for cat in categories:
            mentions.append({
                "teacher": cat,
                "type": "submission",
                "text": post_text.replace("\n", " ")[:500],
                "score": "",
                "permalink": url,
                "created": "",
            })

    # --- expand & scrape comments ---
    expand_comments(driver, MAX_LOAD_MORE_CLICKS)

    comment_divs = driver.find_elements(By.CSS_SELECTOR, "div.comment")
    for c in comment_divs:
        try:
            body_el = c.find_element(By.CSS_SELECTOR, "div.usertext-body div.md")
            body = body_el.text.strip()
        except NoSuchElementException:
            continue
            
        if not body:
            continue
            
        categories = get_teacher_categories(body, names)
        if not categories:
            continue

        try:
            score_el = c.find_element(By.CSS_SELECTOR, "span.score.unvoted")
            score_title = score_el.get_attribute("title") or "0"
        except NoSuchElementException:
            score_title = "0"

        try:
            permalink_el = c.find_element(By.CSS_SELECTOR, "a.bylink")
            permalink = permalink_el.get_attribute("href")
        except NoSuchElementException:
            permalink = url  # fallback, less precise but avoids crashing

        for cat in categories:
            mentions.append({
                "teacher": cat,
                "type": "comment",
                "text": body.replace("\n", " ")[:500],
                "score": score_title,
                "permalink": permalink,
                "created": "",
            })

    return mentions


def collect_mentions(driver, subreddit, names):
    print(f"Searching r/{subreddit} for mentions of: {', '.join(names)}")
    post_links = collect_post_links(driver, subreddit, names)
    print(f"\nFound {len(post_links)} candidate posts. Scanning comments...\n")

    all_mentions = []
    for i, url in enumerate(post_links, 1):
        print(f"  [{i}/{len(post_links)}] {url}")
        try:
            mentions = scrape_post(driver, url, names)
            all_mentions.extend(mentions)
        except Exception as e:
            print(f"      (skipped due to error: {e})")
        time.sleep(1)  # politeness delay between page loads

    return all_mentions


def dedupe_mentions(mentions):
    seen = set()
    unique = []
    for m in mentions:
        key = (m["permalink"], m["teacher"])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    removed = len(mentions) - len(unique)
    if removed:
        print(f"Removed {removed} duplicate mention(s).")
    return unique


def analyze_sentiment(mentions):
    sia = SentimentIntensityAnalyzer()
    for m in mentions:
        score = sia.polarity_scores(m["text"])["compound"]
        m["sentiment_score"] = score
        if score >= 0.25:
            m["sentiment"] = "positive"
        elif score <= -0.25:
            m["sentiment"] = "negative"
        else:
            m["sentiment"] = "neutral"
    return mentions


def print_summary(mentions, teacher_label):
    if not mentions:
        print(f"\nNo mentions found for {teacher_label}. Try adding more name "
              f"variants (nickname, last name only, with/without title) or "
              f"check the subreddit name is correct.")
        return

    pos = [m for m in mentions if m["sentiment"] == "positive"]
    neg = [m for m in mentions if m["sentiment"] == "negative"]
    neu = [m for m in mentions if m["sentiment"] == "neutral"]
    total = len(mentions)

    print("\n" + "=" * 60)
    print(f"SUMMARY for {teacher_label}")
    print("=" * 60)
    print(f"Total mentions found: {total}")
    print(f"  Positive: {len(pos)} ({len(pos)/total*100:.0f}%)")
    print(f"  Negative: {len(neg)} ({len(neg)/total*100:.0f}%)")
    print(f"  Neutral:  {len(neu)} ({len(neu)/total*100:.0f}%)")

    avg_score = sum(m["sentiment_score"] for m in mentions) / total
    print(f"\nAverage sentiment score: {avg_score:.2f} (-1 = very negative, +1 = very positive)")

    def top(lst, n=3):
        def score_key(m):
            try:
                return int(str(m["score"]).split()[0])
            except (ValueError, IndexError):
                return 0
        return sorted(lst, key=score_key, reverse=True)[:n]

    if pos:
        print("\n--- Top positive mentions ---")
        for m in top(pos):
            print(f"  ({m['score']}) {m['text'][:150]}")
            print(f"     {m['permalink']}")
    if neg:
        print("\n--- Top negative mentions ---")
        for m in top(neg):
            print(f"  ({m['score']}) {m['text'][:150]}")
            print(f"     {m['permalink']}")

    print("\nFull details saved to CSV — read the raw comments yourself, "
          "sentiment analysis on short slangy text isn't perfect.")


def build_summary_row(mentions, teacher_label):
    total = len(mentions)
    pos = sum(1 for m in mentions if m["sentiment"] == "positive")
    neg = sum(1 for m in mentions if m["sentiment"] == "negative")
    neu = sum(1 for m in mentions if m["sentiment"] == "neutral")
    avg_score = sum(m["sentiment_score"] for m in mentions) / total if total else 0

    if avg_score >= 0.25:
        verdict = "Liked"
    elif avg_score <= -0.25:
        verdict = "Disliked"
    else:
        verdict = "Mixed/Neutral"

    return {
        "teacher": teacher_label,
        "total_mentions": total,
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "avg_sentiment_score": round(avg_score, 3),
        "overall_verdict": verdict,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def update_summary_csv(filename, new_row):
    """One row per professor; updates in place across runs instead of
    appending duplicate rows for the same professor."""
    fieldnames = ["teacher", "total_mentions", "positive", "negative",
                  "neutral", "avg_sentiment_score", "overall_verdict", "last_updated"]
    rows = {}

    if os.path.exists(filename):
        with open(filename, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows[row["teacher"]] = row

    rows[new_row["teacher"]] = new_row

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows.values():
            writer.writerow(row)

    print(f"Updated master summary: {filename} ({len(rows)} professor(s) total)")


def save_csv(mentions, filename):
    if not mentions:
        return
    if os.path.exists(filename):
        os.remove(filename)
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "teacher", "type", "sentiment", "sentiment_score", "score", "created", "text", "permalink"
        ])
        writer.writeheader()
        for m in mentions:
            writer.writerow(m)
    print(f"\nSaved {len(mentions)} mentions to {filename}")


def main():
    parser = argparse.ArgumentParser(description="Scrape a subreddit (via real browser/account) for sentiment about a teacher.")
    parser.add_argument("subreddit", help="Subreddit name, with or without r/ prefix")
    parser.add_argument("names", nargs="+", help="Teacher name(s) / variants to search for")
    args = parser.parse_args()

    subreddit_name = args.subreddit.replace("r/", "").replace("/r/", "").strip()

    driver = setup_driver()
    try:
        ensure_login(driver)
        mentions = collect_mentions(driver, subreddit_name, args.names)
    finally:
        driver.quit()

    mentions = dedupe_mentions(mentions)
    mentions = analyze_sentiment(mentions)

    grouped = defaultdict(list)
    for m in mentions:
        grouped[m["teacher"]].append(m)
        
    if not grouped:
        print_summary([], args.names[0])
        
    for teacher_label, teacher_mentions in grouped.items():
        print_summary(teacher_mentions, teacher_label)

        safe_name = "".join(c if c.isalnum() else "_" for c in teacher_label)
        save_csv(teacher_mentions, f"{safe_name}_reddit_mentions.csv")

        summary_row = build_summary_row(teacher_mentions, teacher_label)
        update_summary_csv("teacher_review_summary.csv", summary_row)


if __name__ == "__main__":
    main()


    #python red.py r/Vit "Professor Manikandan" "Manikandan"