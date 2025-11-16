import os

class Config:
    # Secret key required to handle Flask session
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret")

    # PostgreSQL connection string
    # Format: postgresql+psycopg2://username:password@host:port/dbname
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "FedosFedos")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "app")

    DATABASE_URL = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
