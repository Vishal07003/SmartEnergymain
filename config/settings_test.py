import os
from config.settings import *

# In-memory SQLite for test execution when PostgreSQL user lacks CREATEDB privileges
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Fast password hashing for instant unit/integration tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

