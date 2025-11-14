from flask import Blueprint

# Blueprint for rendering admin HTML pages
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Blueprint for admin-related APIs, maintaining the original URL structure
api_admin_bp = Blueprint('api_admin', __name__, url_prefix='/api/admin')

# Import the routes to register them with the blueprints
from . import pages, user_api, appointment_api, config_api, schedule_api, test_api