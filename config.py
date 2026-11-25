import os

class Config:
    SECRET_KEY = os.environ.get("NEWS_PULSE_SECRET", "newspulse-local-development-key")
    DEMO_USERNAME = os.environ.get("NEWS_PULSE_USERNAME", "user")
    DEMO_PASSWORD = os.environ.get("NEWS_PULSE_PASSWORD", "user123")
