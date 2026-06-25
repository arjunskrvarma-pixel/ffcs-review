# Reddit Teacher Review Scraper 📊

A Python-based web scraper that uses Selenium to automate a Chrome browser, search a specific subreddit for mentions of a teacher or professor, and perform sentiment analysis on the posts and comments.

## ✨ Features
* **No API Keys Required:** Uses an actual browser session, bypassing the need for Reddit API access.
* **Smart Initial Detection:** Automatically detects initials next to a professor's name (e.g., differentiating between "Manikandan N" and "Manikandan G" automatically) and creates separate summaries for each.
* **Sentiment Analysis:** Utilizes NLTK's VADER lexicon to score each comment as Positive, Negative, or Neutral.
* **CSV Export:** Generates individual CSV files for each professor detected, and maintains a master summary file (`teacher_review_summary.csv`).
* **Persistent Login:** Saves your Chrome profile locally so you only need to log in to Reddit once!

---

## 🚀 Setup Instructions (One-time)

1. **Install Dependencies:**
   Make sure you have Python installed, then install the required libraries:
   ```bash
   pip install selenium nltk
   ```

2. **Browser Requirements:**
   Make sure you have Google Chrome installed on your computer. Selenium 4.10+ will automatically download the matching ChromeDriver for you, so no manual driver setup is needed!

3. **First Run & Login:**
   Run the script for the first time:
   ```bash
   python red.py r/YourCollegeSubreddit "Professor Name"
   ```
   A Chrome window will open. The **FIRST** time you run this:
   * It will pause and ask you to log into your Reddit account manually in that window.
   * Once logged in, press `Enter` in your terminal to continue.
   * Your session is saved locally (in a `./chrome_profile` folder), so you won't need to log in again on future runs.

---

## 💻 Usage

Run the script by providing the subreddit (with or without `r/`) and the name(s) or variants you want to search for.

**Basic Example:**
```bash
python red.py r/Vit Manikandan
```

**Multiple Name Variants:**
```bash
python red.py Vit "Professor Smith" "John Smith" "Smith"
```

### 🧠 How Smart Grouping Works:
If you search for a generic name like "Manikandan", the script will automatically read the context of the comments to find initials. It will group the results and output:
* A summary for **Manikandan N**
* A summary for **Manikandan G**
* A summary for **Manikandan (Unspecified)** (if no initial was found)

---

## ⚠️ Important Notes
* **Speed:** This script loads actual web pages instead of using an API, so it is naturally slower. Large comment threads are only partially expanded to keep runtime reasonable.
* **Fragility:** Web scrapers rely on HTML structure. This scraper targets `old.reddit.com` as it is much more reliable to scrape than the modern React-based Reddit. If Reddit changes the HTML of old.reddit.com, selectors in the code may need updating.
* **Rate Limiting:** Automated browsing is technically against Reddit's Terms of Service. This script includes built-in `time.sleep()` delays between page loads to be polite. Please keep your request volume reasonable to avoid temporary IP bans.
