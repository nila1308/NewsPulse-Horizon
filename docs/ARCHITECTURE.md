# NewsPulse Architecture

```text
User
 |
 v
Flask Web Application
 |             |
 |             +--> Login / Session
 |
 +--> RSS Scraper (Requests + BeautifulSoup XML)
 |          |
 |          v
 |      Google News RSS
 |
 +--> JSON Storage (headlines and bookmarks)
 |
 +--> Dashboard (Jinja + CSS + JavaScript)
 |
 +--> Article Reader
            |
            v
      Publisher HTML page
            |
            v
      BeautifulSoup text extraction
            |
            v
      Article content or original-source fallback
```
