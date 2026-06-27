# Reddit Teacher Review Scraper

A Python scraper that uses Selenium to search old Reddit for professor or teacher mentions, then scores each matched post/comment with NLTK VADER sentiment analysis.

## Features

* Uses a real Chrome session, so no Reddit API key is required.
* Keeps a local Chrome profile in `chrome_profile` so you only need to log in once.
* Searches multiple name variants in one run.
* Groups generic names by nearby initials, such as `Manikandan N` vs `Manikandan G`.
* Treats official discussion-thread boilerplate as neutral.
* Adds a small student-slang sentiment lexicon for words like `chill`, `lenient`, `strict`, and `harsh`.
* Exports per-professor CSV files and a master `teacher_review_summary.csv`.

## Setup

Install Python dependencies:

```bash
pip install selenium nltk
```

Make sure Google Chrome is installed. Selenium Manager can download the matching ChromeDriver automatically for current Selenium versions.

## Usage

Basic run:

```bash
python red.py r/YourSubreddit "Professor Name"
```

Multiple name variants:

```bash
python red.py VIT "Manikandan" "Professor Manikandan" "Manikandan N"
```

Useful options:

```bash
python red.py VIT Manikandan --pages 5 --load-more 8 --delay 1.5 --output-dir results
```

Available flags:

* `--headless` runs Chrome without a visible browser window.
* `--pages` controls how many search-result pages to scan per name.
* `--load-more` controls how many "load more comments" clicks happen per post.
* `--delay` controls the delay after page loads.
* `--profile-dir` changes where the Chrome login profile is stored.
* `--output-dir` changes where CSV outputs are written.

## First Login

On the first non-headless run, Chrome opens old Reddit and the script pauses. Log in manually, then return to the terminal and press Enter. The login session is reused from the profile directory on later runs.

## Output

For every detected professor group, the script writes:

* `<Professor_Name>_reddit_mentions.csv`
* `teacher_review_summary.csv`

The summary CSV is updated in place, with one row per professor.

## Notes

This scraper targets `old.reddit.com`, which is more stable for Selenium scraping than modern Reddit. Keep the delays reasonable and avoid high-volume runs.
This project aggregates publicly available Reddit discussions and applies automated sentiment analysis using NLTK VADER. Results are approximate and should not be interpreted as factual ratings of any individual. Reddit opinions may be biased or unrepresentative.
