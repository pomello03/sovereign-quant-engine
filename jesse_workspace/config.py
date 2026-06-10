# jesse_workspace/config.py
# Reference: https://docs.jesse.trade/

import os

config = {
    # database connection details
    'databases': {
        'postgres': {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 5432)),
            'database': os.environ.get('DB_NAME', 'jesse_db'),
            'username': os.environ.get('DB_USER', 'jesse_user'),
            'password': os.environ.get('DB_PASSWORD', 'jesse_password'),
            'schema': 'public',
        }
    },

    'caching': {
        'driver': 'redis',
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'password': None,
    },

    'logging': {
        'info': True,
        'warn': True,
        'error': True,
        'balance_update': True,
        'order_submission': True,
        'order_cancellation': True,
        'order_execution': True,
        'position_opened': True,
        'position_closed': True,
        'position_liquidated': True,
        'position_adjusted': True,
    }
}
