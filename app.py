from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from functools import wraps
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import Path
import requests, csv, io, json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from config import Config
from storage import load_json, save_json

app = Flask(__name__)
app.config.from_object(Config)

@app.context_processor
def inject_site_helpers():
    return {"reading_time": reading_time, "load_notification_badge": len(load_notifications()) if session.get("logged_in") else 0}
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CATEGORIES = ["Sports", "Entertainment", "Education", "Technology", "Business", "Science", "Health"]
CATEGORY_QUERIES = {
    "Sports": "sports news India",
    "Entertainment": "entertainment news India",
    "Education": "education news India",
    "Technology": "technology news India",
    "Business": "business news India",
    "Science": "science news",
    "Health": "health news India",
}
HEADLINES_FILE = DATA_DIR / "headlines.json"
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
HISTORY_FILE = DATA_DIR / "reading_history.json"
NOTIFICATIONS_FILE = DATA_DIR / "notifications.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsPulse/2.0; educational news reader)"}
CATEGORY_INFO = {
    "Sports": {"description": "Follow the latest action from cricket, football, tennis and more. Explore tournament results, team updates, athlete achievements and the stories shaping the world of sport.", "image": "/static/images/sports.jpg"},
    "Entertainment": {"description": "Catch up on films, television, music and popular culture. Discover new releases, industry updates, award events and noteworthy stories from the entertainment world.", "image": "/static/images/entertainment.jpg"},
    "Education": {"description": "Explore developments in schools, colleges, learning and education policy. Read about examinations, research, scholarships, campus news and changing approaches to education.", "image": "/static/images/education.jpg"},
    "Technology": {"description": "Discover the latest in artificial intelligence, gadgets, software and digital innovation. Follow product launches, scientific breakthroughs and technology trends influencing everyday life.", "image": "/static/images/technology.jpg"},
    "Business": {"description": "Stay informed about companies, markets, jobs and the wider economy. Follow business decisions, financial developments, entrepreneurship and trends shaping industries.", "image": "/static/images/business.jpg"},
    "Science": {"description": "Read about discoveries, space exploration, climate research and new scientific ideas. Understand the studies and innovations expanding knowledge about our world and beyond.", "image": "/static/images/science.jpg"},
    "Health": {"description": "Follow public health updates, medical research and healthcare innovation. Find informative coverage of health systems, prevention, wellbeing and developments in medical science.", "image": "/static/images/health.jpg"},
}

def load_articles():
    items = load_json(HEADLINES_FILE, [])
    if not items:
        # Restore the bundled preloaded edition if the live-feed file is empty.
        seed_file = DATA_DIR / "preloaded_articles.json"
        items = load_json(seed_file, [])
        if items:
            save_json(HEADLINES_FILE, items)
    return items

def save_articles(items):
    save_json(HEADLINES_FILE, items)

def load_bookmarks():
    return load_json(BOOKMARKS_FILE, [])

def load_history():
    return load_json(HISTORY_FILE, [])

def record_view(item):
    history = load_history()
    history.insert(0, {"id": item.get("id"), "viewed_at": datetime.now(timezone.utc).isoformat()})
    save_json(HISTORY_FILE, history[:250])

def unique_recent_history():
    seen, result = set(), []
    for entry in load_history():
        key = entry.get("id")
        if key and key not in seen:
            seen.add(key); result.append(entry)
        if len(result) >= 20:
            break
    return result

def load_notifications():
    return load_json(NOTIFICATIONS_FILE, [])

def reading_time(item):
    body = item.get("preloaded_content") or []
    words = len(" ".join(str(x) for x in body).split())
    if not words:
        words = len((item.get("description") or "").split())
    return max(1, (words + 219) // 220)

def popularity_score(item, bookmarks, history):
    key = item.get("id")
    saved = 3 if key in bookmarks else 0
    viewed = sum(1 for row in history if row.get("id") == key)
    return saved + viewed * 2

def article_id(url):
    import hashlib
    return hashlib.sha1(url.encode("utf-8", errors="ignore")).hexdigest()[:16]

def _image_from_feed_item(item):
    """Extract the actual story image from RSS media fields or embedded HTML."""
    candidates = []
    # RSS media/enclosure fields are usually the most reliable source.
    for node in item.find_all(True):
        tag_name = (node.name or "").lower()
        if tag_name in ("media:content", "media:thumbnail", "enclosure") or tag_name.endswith(("content", "thumbnail")):
            if (node.get("type", "").lower().startswith("image/") or
                    tag_name in ("media:content", "media:thumbnail") or
                    tag_name.endswith("thumbnail")):
                candidates.extend([node.get("url"), node.get("href")])

    # IMPORTANT: parse the raw HTML, not get_text(), otherwise embedded <img>
    # tags in RSS descriptions are discarded.
    for node in item.find_all(["content", "description", "encoded"]):
        html = str(node)
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            candidates.extend([img.get("src"), img.get("data-src"), img.get("data-original")])
            srcset = img.get("srcset", "")
            if srcset:
                candidates.append(srcset.split(",")[0].strip().split(" ")[0])

    for candidate in candidates:
        if not candidate:
            continue
        candidate = str(candidate).strip()
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        if candidate.startswith(("https://", "http://")) and not _looks_like_news_logo(candidate):
            return candidate
    return ""

def _looks_like_news_logo(value):
    """Reject obvious feed/provider logos so they are not shown as story photos."""
    text = str(value or "").lower()
    blocked = ("news.google.com", "google.com/images/branding", "google_news",
               "google-news-logo", "favicon", "sprite", "logo.svg")
    return any(token in text for token in blocked)

def _publisher_image(url):
    """Best-effort Open Graph/Twitter image lookup; never bypasses publisher restrictions."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=(3, 4), allow_redirects=True)
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            return ""
        soup = BeautifulSoup(response.text[:900000], "html.parser")
        for selector in [("meta", {"property": "og:image"}), ("meta", {"name": "twitter:image"}), ("meta", {"property": "og:image:url"})]:
            tag = soup.find(*selector)
            if tag and tag.get("content"):
                image = requests.compat.urljoin(response.url, tag["content"].strip())
                if image.startswith(("https://", "http://")) and not _looks_like_news_logo(image):
                    return image
    except requests.RequestException:
        pass
    except Exception:
        pass
    return ""

def _cache_remote_image(image_url, article_key):
    """Download a publisher image into static storage so cards do not rely on hotlinks."""
    if not image_url or not image_url.startswith(("https://", "http://")):
        return ""
    import hashlib
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=(3, 5), stream=True, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        extensions = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
                      "image/webp": ".webp", "image/gif": ".gif", "image/avif": ".avif"}
        extension = extensions.get(content_type)
        if not extension:
            return ""
        folder = Path("static") / "images" / "news"
        folder.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256((article_key + image_url).encode("utf-8", errors="ignore")).hexdigest()[:24]
        destination = folder / f"{digest}{extension}"
        if destination.exists() and destination.stat().st_size > 0:
            return "/static/images/news/" + destination.name
        total = 0
        with destination.open("wb") as image_file:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 8 * 1024 * 1024:
                    image_file.close()
                    destination.unlink(missing_ok=True)
                    return ""
                image_file.write(chunk)
        if total < 1024:
            destination.unlink(missing_ok=True)
            return ""
        return "/static/images/news/" + destination.name
    except Exception:
        return ""

def fetch_category(category, limit=10):
    query = requests.utils.quote(CATEGORY_QUERIES[category])
    feed_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    response = requests.get(feed_url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "xml")
    results = []
    for item in soup.find_all("item")[:limit]:
        title = item.title.get_text(" ", strip=True) if item.title else "Untitled"
        link = item.link.get_text(strip=True) if item.link else ""
        description_html = item.description.get_text(" ", strip=True) if item.description else ""
        description = BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)
        pub = item.pubDate.get_text(strip=True) if item.pubDate else ""
        source = item.source.get_text(strip=True) if item.source else "News source"
        if not link:
            continue
        results.append({
            "id": article_id(link), "title": title, "url": link,
            "description": description[:500], "published": pub,
            "source": source, "category": category,
            "image": _image_from_feed_item(item), "fetched_at": datetime.now(timezone.utc).isoformat()
        })
    # Image discovery and downloads are handled once, centrally, after all feeds
    # have been collected. This avoids waiting for images category-by-category.
    return results

def _finish_article_image(article):
    """Resolve and cache one article image; use category artwork as a safe fallback."""
    image = article.get("image", "")
    # Old auto-downloaded images may be provider logos. Recheck those once using
    # the corrected RSS extraction before falling back to category artwork.
    if str(image).startswith("/static/images/news/"):
        image = ""
    if not image:
        image = _publisher_image(article.get("url", ""))
    if image.startswith(("https://", "http://")):
        image = _cache_remote_image(image, article.get("id", "")) or ""
    if not image.startswith("/static/"):
        image = CATEGORY_INFO.get(article.get("category"), {}).get(
            "image", "/static/images/image-unavailable.svg")
    article["image"] = image
    return article

def fetch_all_categories():
    collected, errors = [], []
    # Fetch all seven RSS feeds at the same time instead of waiting category-by-category.
    with ThreadPoolExecutor(max_workers=len(CATEGORIES)) as pool:
        jobs = {pool.submit(fetch_category, category): category for category in CATEGORIES}
        for future in as_completed(jobs):
            category = jobs[future]
            try:
                collected.extend(future.result())
            except requests.RequestException as exc:
                errors.append(f"{category}: {exc.__class__.__name__}")
            except Exception:
                errors.append(f"{category}: feed parsing error")

    # Merge by URL and keep already-cached local images. Only process images for
    # new or not-yet-cached stories, rather than downloading them on every refresh.
    previous = load_articles()
    merged = {item.get("url"): item for item in previous if item.get("url")}
    images_to_process = []
    for item in collected:
        old = merged.get(item["url"], {})
        old_image = old.get("image", "")
        old_path = str(old_image).split("?", 1)[0]
        old_is_curated = old_path.startswith("/static/images/articles/") or old_path.startswith("/static/images/") and "/news/" not in old_path
        selected_image = old_image if old_is_curated else (item.get("image") or "")

        merged[item["url"]] = {**old, **item, "image": selected_image}
        if not old_is_curated:
            images_to_process.append(merged[item["url"]])

    # Resolve/cache multiple images together. Existing cached images are skipped.
    if images_to_process:
        with ThreadPoolExecutor(max_workers=20) as pool:
            image_jobs = [pool.submit(_finish_article_image, article) for article in images_to_process]
            for future in as_completed(image_jobs):
                try:
                    future.result()
                except Exception:
                    pass

    items = list(merged.values())
    items.sort(key=lambda x: x.get("published", ""), reverse=True)
    if items:
        save_articles(items)
    return items, errors

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == Config.DEMO_USERNAME and password == Config.DEMO_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            if not load_articles():
                items, errors = fetch_all_categories()
                if not items:
                    flash("News feeds could not be reached. Open the dashboard and try Refresh News.", "warning")
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    items = load_articles()
    category = request.args.get("category", "All")
    keyword = request.args.get("q", "").strip().lower()
    sort = request.args.get("sort", "latest")
    filtered = [a for a in items if category == "All" or a.get("category") == category]
    if keyword:
        filtered = [a for a in filtered if keyword in (a.get("title", "") + " " + a.get("description", "")).lower()]
    filtered.sort(key=lambda a: a.get("published", ""), reverse=(sort == "latest"))
    bookmarks = set(load_bookmarks())
    top_stories = filtered[:4]
    counts = {c: sum(1 for a in items if a.get("category") == c) for c in CATEGORIES}
    return render_template("dashboard.html", articles=filtered, categories=CATEGORIES,
                           selected_category=category, keyword=request.args.get("q", ""),
                           sort=sort, bookmarks=bookmarks, top_stories=top_stories,
                           counts=counts, total=len(items), category_info=CATEGORY_INFO,
                           history=unique_recent_history(), recent_notifications=len(load_notifications()))

@app.route("/refresh", methods=["POST"])
@login_required
def refresh():
    before = {a.get("url") for a in load_articles()}
    items, errors = fetch_all_categories()
    new_items = [a for a in items if a.get("url") not in before]
    if new_items:
        notes = load_notifications()
        for item in new_items[:20]:
            notes.insert(0, {"title": item.get("title", "New story"), "category": item.get("category", "News"),
                            "source": item.get("source", "Publisher"), "url": item.get("url", ""),
                            "created_at": datetime.now(timezone.utc).isoformat()})
        save_json(NOTIFICATIONS_FILE, notes[:100])
    if items:
        flash(f"News updated: {len(items)} articles collected.", "success")
    else:
        flash("Could not fetch live feeds. Check your internet connection and try again.", "warning")
    if errors:
        flash("Some categories could not be refreshed: " + ", ".join(errors), "warning")
    return redirect(url_for("dashboard"))

@app.route("/latest")
@login_required
def latest():
    items = load_articles()
    items.sort(key=lambda a: a.get("published", ""), reverse=True)
    return render_template("dashboard.html", articles=items, categories=CATEGORIES, selected_category="All",
                           keyword="", sort="latest", bookmarks=set(load_bookmarks()), top_stories=items[:4],
                           counts={c: sum(1 for a in items if a.get("category") == c) for c in CATEGORIES},
                           total=len(items), category_info=CATEGORY_INFO, page_title="Latest News", nav_page="latest")

@app.route("/trending")
@login_required
def trending():
    items = load_articles()
    bookmarks = set(load_bookmarks())
    history = load_history()
    items.sort(key=lambda a: (popularity_score(a, bookmarks, history), a.get("published", "")), reverse=True)
    return render_template("dashboard.html", articles=items, categories=CATEGORIES, selected_category="All",
                           keyword="", sort="latest", bookmarks=bookmarks, top_stories=items[:4],
                           counts={c: sum(1 for a in items if a.get("category") == c) for c in CATEGORIES},
                           total=len(items), category_info=CATEGORY_INFO, page_title="Popular on NewsPulse", nav_page="trending")

@app.route("/history")
@login_required
def history():
    all_items = {a.get("id"): a for a in load_articles()}
    ordered = [all_items[row.get("id")] for row in unique_recent_history() if row.get("id") in all_items]
    return render_template("dashboard.html", articles=ordered, categories=CATEGORIES, selected_category="All",
                           keyword="", sort="latest", bookmarks=set(load_bookmarks()), top_stories=ordered[:4],
                           counts={c: sum(1 for a in ordered if a.get("category") == c) for c in CATEGORIES},
                           total=len(ordered), category_info=CATEGORY_INFO, page_title="Recently Viewed", nav_page="history")

@app.route("/analytics")
@login_required
def analytics():
    items = load_articles(); bookmarks = set(load_bookmarks()); history = load_history()
    counts = {c: sum(1 for a in items if a.get("category") == c) for c in CATEGORIES}
    most_saved = [a for a in items if a.get("id") in bookmarks][:5]
    view_counts = {}
    for row in history: view_counts[row.get("id")] = view_counts.get(row.get("id"), 0) + 1
    most_viewed = sorted([a for a in items if a.get("id") in view_counts], key=lambda a: view_counts[a.get("id")], reverse=True)[:5]
    return render_template("analytics.html", counts=counts, total=len(items), bookmarks=len(bookmarks),
                           views=len(history), most_saved=most_saved, most_viewed=most_viewed, categories=CATEGORIES)

@app.route("/notifications")
@login_required
def notifications():
    return render_template("notifications.html", notifications=load_notifications())

@app.route("/preferences")
@login_required
def preferences():
    return render_template("preferences.html")

@app.route("/article/<article_key>")
@login_required
def article(article_key):
    items = load_articles()
    item = next((a for a in items if a.get("id") == article_key), None)
    if not item:
        flash("That article is no longer in the saved feed. Refresh the news and try again.", "warning")
        return redirect(url_for("dashboard"))
    record_view(item)
    if item.get("external_only"):
        content = []
        image = item.get("image", "")
        final_url = item.get("url", "")
        message = "This story is hosted by the original publisher. Use the link below to read the publisher's version."
    elif item.get("preloaded_content"):
        content = item["preloaded_content"]
        image = item.get("image", "")
        final_url = ""
        message = "This is an original preloaded NewsPulse editorial explainer, not a live news report."
    elif item.get("is_sample"):
        content = []
        image = item.get("image", "")
        final_url = ""
        message = "The headline and summary are preloaded. Full sample text is included in 10 selected stories."
    else:
        content, image, final_url, message = extract_article(item["url"])
    ordered = load_articles()
    index = next((i for i, row in enumerate(ordered) if row.get("id") == article_key), 0)
    previous_item = ordered[index-1] if index > 0 else None
    next_item = ordered[index+1] if index + 1 < len(ordered) else None
    minutes = reading_time(item)
    return render_template("article.html", article=item, content=content, image=image or item.get("image", ""),
                           final_url=final_url, message=message, reading_minutes=minutes,
                           previous_item=previous_item, next_item=next_item)

def extract_article(url):
    """Extract publicly available article text. This is best-effort, not a bypass for paywalls."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return [], "", url, "This link is not a supported web address."
        response = requests.get(url, headers=HEADERS, timeout=18, allow_redirects=True)
        final_url = response.url
        if response.status_code in (401, 403, 429):
            return [], "", final_url, "The publisher restricts automated access to this page."
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for node in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"]):
            node.decompose()
        image = ""
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image = og["content"]
        candidates = []
        for selector in ["article", "main", '[role="main"]', ".article-body", ".story-body", ".story-content", ".content"]:
            candidates.extend(soup.select(selector))
        root = max(candidates, key=lambda el: len(el.get_text(" ", strip=True)), default=soup.body or soup)
        paragraphs = []
        for p in root.find_all(["p", "h2", "h3"]):
            text = p.get_text(" ", strip=True)
            if len(text) > 45 and text not in paragraphs:
                paragraphs.append(text)
        if len(paragraphs) < 2:
            return [], image, final_url, "The publisher page did not expose enough readable article text. Use the original article link below."
        return paragraphs[:80], image, final_url, ""
    except requests.RequestException:
        return [], "", url, "The article could not be retrieved right now. The publisher may be unavailable or may restrict automated access."
    except Exception:
        return [], "", url, "NewsPulse could not identify the article text on this page."

@app.route("/bookmark/<article_key>", methods=["POST"])
@login_required
def bookmark(article_key):
    saved = load_bookmarks()
    if article_key in saved:
        saved.remove(article_key)
        flash("Bookmark removed.", "success")
    else:
        saved.append(article_key)
        flash("Article bookmarked.", "success")
    save_json(BOOKMARKS_FILE, saved)
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/bookmarks")
@login_required
def bookmarks():
    saved = set(load_bookmarks())
    items = [a for a in load_articles() if a.get("id") in saved]
    return render_template("dashboard.html", articles=items, categories=CATEGORIES,
                           selected_category="All", keyword="", sort="latest",
                           bookmarks=saved, top_stories=items[:4], counts={c: 0 for c in CATEGORIES},
                           total=len(items), page_title="Bookmarked Articles", category_info=CATEGORY_INFO,
                           history=unique_recent_history(), recent_notifications=len(load_notifications()), nav_page="bookmarks")

@app.route("/export/csv")
@login_required
def export_csv():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["title", "category", "source", "published", "description", "url"])
    writer.writeheader()
    for item in load_articles():
        writer.writerow({k: item.get(k, "") for k in writer.fieldnames})
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=newspulse_headlines.csv"})

@app.route("/export/excel")
@login_required
def export_excel():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "NewsPulse Headlines"
    headers = ["Title", "Category", "Source", "Published", "Description", "URL"]
    ws.append(headers)
    for item in load_articles():
        ws.append([item.get(k, "") for k in ["title", "category", "source", "published", "description", "url"]])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return Response(stream.getvalue(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=newspulse_headlines.xlsx"})

if __name__ == "__main__":
    app.run(debug=True)
