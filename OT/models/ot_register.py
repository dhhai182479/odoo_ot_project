from odoo import fields, models, api, _
from datetime import datetime, date, time, timedelta
import pytz
from odoo.exceptions import UserError, AccessError, ValidationError
import holidays

class OtRegistration(models.Model):
    _name = 'ot.registration'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _rec_name = 'project_id'

    ot_lines_ids = fields.One2many('ot.registration.lines', 'ot_registration_id', string='OT Lines')
    project_id = fields.Many2one('project.project', string='Project', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True,
                                  default=lambda self: self._get_default_employee())
    manager_id = fields.Many2one('hr.employee', string='Approve', required=True)
    ot_month = fields.Date(string='OT Month', readonly=True, default=date.today())
    dl_manager_id = fields.Many2one('hr.employee', compute='_compute_dl_manager',
                                    string='Department lead', readonly=True, store=True)
    additional_hours = fields.Float('Total OT', compute='_compute_sum_ot_hours', store=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('to_approve', 'To Approve'), ('approved', 'PM Approved'),
        ('done', 'DL Approved'), ('refused', 'Refused')
    ], string='State', default='draft', readonly=True, track_visibility='onchange')

    def _get_default_employee(self):
        return self.env['hr.employee'].sudo().search([('user_id', '=', self._uid)], limit=1)

    @api.depends('employee_id')
    def _compute_dl_manager(self):
        for r in self:
            if r.employee_id:
                r.dl_manager_id = r.employee_id.parent_id.id

    @api.depends('ot_lines_ids', 'ot_lines_ids.additional_hours')
    def _compute_sum_ot_hours(self):
        for r in self:
            if r.ot_lines_ids:
                additional_hours = 0
                for record in r.ot_lines_ids:
                    additional_hours += record.additional_hours
                    # r.additional_hours = sum(r.ot_lines.mapped('additional_hours'))
                r.additional_hours = additional_hours

    @api.multi
    def send_mail_emp_to_pm(self):
        template = self.env.ref('OT.email_template_ot_emp_to_pm')
        for r in self:
            self.env['mail.template'].browse(template.id).send_mail(r.id)

    @api.multi
    def send_mail_pm_approve(self):
        template = self.env.ref('OT.email_template_ot_pm_to_emp')
        for r in self:
            self.env['mail.template'].browse(template.id).send_mail(r.id)

    @api.multi
    def send_mail_pm_refused(self):
        template = self.env.ref('OT.email_template_ot_pm_refused')
        for r in self:
            self.env['mail.template'].browse(template.id).send_mail(r.id)

    @api.multi
    def send_mail_dl_approve(self):
        template = self.env.ref('OT.email_template_ot_dl_to_emp')
        for r in self:
            self.env['mail.template'].browse(template.id).send_mail(r.id)

    @api.multi
    def send_mail_dl_refused(self):
        template = self.env.ref('OT.email_template_ot_dl_refused')
        for r in self:
            self.env['mail.template'].browse(template.id).send_mail(r.id)

    def action_draft(self):
        for r in self:
            if r.env.user.has_group('OT.group_ot_employee') and r.state == 'refused':
                r.state = 'draft'
            else:
                raise ValidationError(_('you do not have permission to make the request'))

    def action_submit(self):
        for r in self:
            if r.env.user.has_group('OT.group_ot_employee') and r.state == 'draft':
                r.state = 'to_approve'
                self.send_mail_emp_to_pm()
            else:
                raise ValidationError(_('you do not have permission to make the request'))

    def action_button_pm_dl_approve(self):
        for r in self:
            if r.env.user.has_group('OT.group_ot_pm') and r.state == 'to_approve':
                r.state = 'approved'
                self.send_mail_pm_approve()
            elif r.env.user.has_group('OT.group_ot_dl') and r.state == 'approved':
                r.state = 'done'
                self.send_mail_dl_approve()
            else:
                raise ValidationError(_('you do not have permission to make the request'))

    def action_refused(self):
        for r in self:
            if r.env.user.has_group('OT.group_ot_pm') and r.state == 'to_approve':
                r.state = 'refused'
                self.send_mail_pm_refused()
            elif r.env.user.has_group('OT.group_ot_dl') and r.state == 'approved':
                r.state = 'refused'
                self.send_mail_dl_refused()
            else:
                raise ValidationError(_('you do not have permission to make the request'))

    @api.constrains('ot_lines_ids', 'additional_hours')
    def _constrains_ot_lines(self):
        for r in self:
            if not r.ot_lines_ids or r.additional_hours <= 0:
                raise UserError(_('ERROR'))
            if r.ot_lines_ids.category == 'unknown':
                raise UserError(_('Category is not unknown'))

    def unlink(self):
        for r in self:
            if r.state != 'draft':
                raise ValidationError("You can't delete this record because it's not in draft state.")
        return super(OtRegistration, self).unlink()


class OtRegistrationLines(models.Model):
    _name = 'ot.registration.lines'

    ot_registration_id = fields.Many2one('ot.registration', string='OT Registration', ondelete='cascade')
    project_id = fields.Many2one('project.project', string='Project', related='ot_registration_id.project_id',
                                 store=True, related_sudo=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=1, related='ot_registration_id.employee_id',
                                  store=True, related_sudo=True)

    date_from = fields.Datetime(string='From', required=True, default=lambda self: fields.Datetime.now())
    date_to = fields.Datetime(string='To', required=True, default=fields.Datetime.now)
    category = fields.Selection([
        ('normal_day', 'Ngày bình thường'), ('normal_day_morning', 'OT ban ngày (6h-8h30'),
        ('normal_day_night', 'Ngày bình thường - Ban đêm'), ('saturday', 'Thứ 7'),
        ('sunday', 'Chủ nhật'), ('weekend_day_night', 'Ngày cuối tuần - Ban đêm'),
        ('holiday', 'Ngày lễ'), ('holiday_day_night', 'Ngày lễ - Ban đêm'),
        ('compensatory_normal', 'Bù ngày lễ vào ngày thường'),('compensatory_night', 'Bù ngày lễ vào ban đêm'),
        ('unknown', 'Không thể xác định')], string='OT Category', readonly=True,
        compute='_compute_check_category', store=True)
    is_wfh = fields.Boolean(string='WFH')
    is_intern_contract = fields.Boolean(string='Is intern', readonly=True)
    additional_hours = fields.Float('OT hours', readonly=True, compute='_compute_count_ot_hours', store=True)
    job_taken = fields.Char(string='Job Taken', default='N/A')
    state = fields.Selection([
        ('draft', 'Draft'), ('to_approve', 'To Approve'), ('approved', 'PM Approved'),
        ('done', 'DL Approved'), ('refused', 'Refused')
    ], string='State', readonly=True, defautl='draft', related="ot_registration_id.state")
    late_approve = fields.Boolean(string='Late approved', readonly=True)
    attendance_notes = fields.Text(string='Attendance Notes', readonly=True)
    notes = fields.Text(readonly=True)
    plan_hours = fields.Char(string='Warning', readonly=True, default='Exceed OT plan')

    @api.depends('date_from', 'date_to')
    def _compute_count_ot_hours(self):
        for r in self:
            if r.date_from and r.date_to:
                additional_hours = (r.date_to - r.date_from).total_seconds()
                additional_hours = round(additional_hours/3600, 2)
                r.additional_hours = additional_hours

    @api.depends('date_from', 'date_to')
    def _compute_check_category(self):
        hour6am = time().replace(hour=6, minute=0, second=0, microsecond=0)
        hour22pm = time().replace(hour=22, minute=0, second=0, microsecond=0)
        hour8h30am = time().replace(hour=8, minute=30, second=0, microsecond=0)
        hour18h30pm = time().replace(hour=18, minute=30, second=0, microsecond=0)
        vi_holidays = holidays.VN()
        for r in self:
            if r.date_from and r.date_to:
                # time_from = r.tz_utc_to_local(r.date_from).time()
                # time_to = r.tz_utc_to_local(r.date_to).time()
                if (r.date_from == r.date_to) and (r.date_from in vi_holidays):
                    r.category = 'holiday'
                elif (r.date_from.isoweekday() or r.date_to.isoweekday()) in (1, 2, 3, 4, 5) and (r.date_from.isoweekday() == r.date_to.isoweekday()):
                    r.category = 'normal_day'
                elif r.date_from.isoweekday() == r.date_to.isoweekday() == 6:
                    if r.date_from in vi_holidays:
                        r.category = 'holiday'
                    else:
                        r.category = 'saturday'
                elif r.date_from.isoweekday() == r.date_to.isoweekday() == 7:
                    if r.date_from in vi_holidays:
                        r.category = 'holiday'
                    else:
                        r.category = 'sunday'
                else:
                    r.category = 'unknown'

    def tz_utc_to_local(self, utc_time):
        return utc_time + self.utc_offset()

    def utc_offset(self):
        user_timezone = self.env.user.tz or 'GMT'
        hours = int(datetime.now(pytz.timezone(user_timezone)).strftime('%z')[:3])
        return timedelta(hours=hours)
