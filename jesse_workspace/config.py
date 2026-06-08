# jesse_workspace/config.py
# Reference: https://docs.jesse.trade/

config = {
    # database connection details
    'databases': {
        'postgres': {
            'host': 'localhost',
            'port': 5432,
            'database': 'jesse_db',
            'username': 'jesse_user',
            'password': 'jesse_password',
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
