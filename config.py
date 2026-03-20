import os

class Config:
    # Secret key required to handle Flask session
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")
