from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Created without an app here on purpose — bound to the Flask app
# via limiter.init_app(app) in app.py. This lets api_routes.py import
# `limiter` directly (e.g. for @limiter.exempt) without a circular
# import back to app.py.
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
