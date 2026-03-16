import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set all required environment variables before any imports
envs = {
    'DATABASE_URL': 'sqlite+aiosqlite:///./test.db',
    'REDIS_URL': 'redis://localhost:6379/0',
    'SECRET_KEY': 'test-secret-key-for-ci-only-64chars-padding-here',
    'JWT_ALGORITHM': 'HS256',
    'GOOGLE_API_KEY': 'dummy-key',
    'GROQ_API_KEY': 'dummy-key',
    'GITHUB_APP_ID': '12345',
    'GITHUB_APP_PRIVATE_KEY': 'dummy-private-key',
    'GITHUB_WEBHOOK_SECRET': 'test-webhook-secret',
    'ENVIRONMENT': 'testing',
    'CELERY_BROKER_URL': 'redis://localhost:6379/0',
    'CELERY_RESULT_BACKEND': 'redis://localhost:6379/0',
    'CORS_ORIGINS': 'http://localhost:3000',
    'STRIPE_SECRET_KEY': 'sk_test_dummy',
    'STRIPE_WEBHOOK_SECRET': 'whsec_dummy',
}
for key, value in envs.items():
    os.environ.setdefault(key, value)
