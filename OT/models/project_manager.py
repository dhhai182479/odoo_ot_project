from odoo import fields, models, api, _

class Project(models.Model):
    _inherit = 'project.project'

    project_manager_id = fields.Many2one('hr.employee', string="Project Manager")