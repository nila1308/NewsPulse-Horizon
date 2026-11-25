# NewsPulse – Features and Logic

## 1. Login
A simple local demonstration login checks the entered credentials against the demo username and password in `config.py`. The password visibility button is handled by JavaScript.

## 2. News collection
The application builds a Google News RSS search URL for each category. Requests downloads the feed and BeautifulSoup parses its XML. Each item is stored with a title, link, description, publication date, source and category.

## 3. Dashboard
Flask sends the saved articles to the Jinja dashboard template. Search checks the title and description. Category and sort filters narrow or reorder the list.

## 4. Article reader
Selecting a headline opens `/article/<id>`. The server requests the publisher URL, removes common navigation and script elements, then looks for an article/main/content container. It extracts readable paragraph and heading text. If the page blocks access or does not expose enough text, the reader shows a message and a link to the publisher.

## 5. Bookmarks and exports
Bookmark IDs are stored in `data/bookmarks.json`. Headlines are stored in `data/headlines.json`. CSV export uses Python's `csv` module; Excel export uses `openpyxl`.

## 6. Theme
The CSS uses theme variables. JavaScript switches between light and dark mode and stores the preference in browser local storage.
