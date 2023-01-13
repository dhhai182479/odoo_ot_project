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


class OtManagement(http.Controller):
    @http.route('/ot_management/<int:id>', type='http', auth='user', website=True)
    def ot_registration_url(self, id):
        menu_id = request.env.ref('ot.menu_ot_registration_request').id
        action_id = request.env.ref('ot.action_ot_registration')
        link_format = "/web?id={}&view_type=form&model=ot.registration&menu_id={}&action={}"
        link = link_format.format(id, menu_id, action_id)
        return request.redirect(link)

