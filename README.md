# NewsPulse Horizon — 68 Article Sample Edition

## Included in this edition
- 68 preloaded original sample/editorial stories across seven categories:
  - Sports: 10
  - Entertainment: 10
  - Education: 10
  - Technology: 10
  - Business: 10
  - Science: 9
  - Health: 9
- 10 stories have expanded preloaded sample text. At least one expanded story is included in every category.
- Seven locally stored, photo-realistic editorial image assets in `static/images/`.
- The preloaded dataset is stored in both `data/headlines.json` and `data/preloaded_articles.json`.
- If `headlines.json` is empty or missing its data, the app restores the bundled preloaded edition.
- Live RSS refresh can add real feed items while retaining the bundled sample stories.

## Important content note
The 68 stories are original demonstration/editorial sample content, not verified breaking-news reports. The seven category images are photo-realistic generated editorial illustrations, stored locally in the project; they are not documentary photographs of the specific events described. Sample items are labelled in the interface.

## Run on Windows
1. Extract this ZIP.
2. Open the `NewsPulse_Horizon` folder in VS Code.
3. If dependencies are already installed, run `.\run.bat` in PowerShell.
4. Open http://127.0.0.1:5000
5. Demo login: `user` / `user123`

If setup is required, run:
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`

Keep the PowerShell window open while using the local site. The app stores bookmarks and headlines in the `data` folder.


## Premium Horizon additions

- Editorial spotlight and News Pulsewire latest-headline ticker on the Overview page.
- Latest News and Popular on NewsPulse views (popularity is calculated from local bookmarks and reading activity).
- Persistent reading history and Continue Reading cards.
- News analytics for category distribution, bookmarks and article reading activity.
- Notifications for newly discovered articles after a manual Refresh News operation. These are in-app notices, not operating-system push notifications.
- Reader progress indicator, adjustable text size, share/copy link, estimated reading time, and previous/next story navigation.
- Preferences for theme, reader text size and reduced motion.
- Responsive layouts, hover polish and back-to-top control.

Existing 68-article edition, article content, publisher links, local image assets, category pages, login, bookmarks, exports, search and theme toggle are retained. Reading history and notifications are stored locally in `data/reading_history.json` and `data/notifications.json`.
