import os
class Config:
    SECRET_KEY = os.environ.get("NEWS_PULSE_SECRET", "newspulse-demo-secret-change-before-deployment")
    DEMO_USERNAME = "user"
    DEMO_PASSWORD = "user123"
