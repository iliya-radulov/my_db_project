# Database configuration
# DB_CONFIG = {
#     'host': 'localhost',
#     'port': 5432,
#     'database': 'alloy_lab',
#     'user': 'postgres',
#     'schema': 'alloy_lab'
# }
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': os.environ.get('POSTGRES_PORT', '5432'),
    'database': os.environ.get('POSTGRES_DB', 'alloy_lab'),
    'user': os.environ.get('POSTGRES_USER', 'postgres'),
    'password': os.environ['POSTGRES_PASSWORD'],
    'schema': os.environ.get('POSTGRES_SCHEMA', 'alloy_lab')
}