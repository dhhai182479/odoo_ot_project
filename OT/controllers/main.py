import logging
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo import http, _
import werkzeug

_logger = logging.getLogger(__name__)

class TestController(http.Controller):
    @http.route('/testcontroller', auth='public')
    def test_controller(self):
        return "ABCD"
