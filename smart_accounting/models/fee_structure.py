from dateutil.relativedelta import relativedelta

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
_intervalTypes = {
    'weeks': lambda interval: relativedelta(days=7*interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}
fs = fields.Date.from_string


class AcademicYear(models.Model):
    _inherit = 'academic.year'

    fee_structure_ids = fields.One2many('fee.structure', 'academic_year')


class FeeStructure(models.Model):
    _name = 'fee.structure'
    _rec_name = 'name'
    _description = 'Fees Structure'

    # @api.model
    # def get_current_academic_year(self):
    #     return int(self.env['ir.config_parameter'].sudo().get_param('smartschool.current_academic_year'))

    name = fields.Char(string='Name', required=True)
    description = fields.Char(string='Description')
    fee_group = fields.Many2one('fee.group', string='Group')
    academic_year = fields.Many2one('academic.year', 'Academic Year', required=True,
                                    default=lambda self: self.env.user.company_id.current_academic_year.id)
    one_time_fees = fields.One2many('fee.structure.line', 'fee_structure_id',
                                    domain=[('generation_type', '=', 'one_time')])
    recurring_fees = fields.One2many('fee.structure.line', 'fee_structure_id',
                                     domain=[('generation_type', '=', 'recurring')])

    fee_structure_lines = fields.One2many('fee.structure.line', 'fee_structure_id')
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.user.company_id.id,
                                 required=True)
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'),
                              ('inactive', 'Inactive'), ('expired', 'Expired')], default='draft', required=True)
    student_ids = fields.One2many('ss.student', 'fee_structure_id')

    fee_ids = fields.One2many('ss.fee', 'fee_structure_id', readonly=True)
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Name must be unique.')
    ]

    @api.multi
    def action_view_fees(self):
        return {
            'name': _("Fees from FS: %s" % self.name),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'ss.fee',
            'domain': [('id', 'in', self.fee_ids.ids)]
        }

    @api.multi
    def set_to_draft(self):
        for line in self.one_time_fees | self.recurring_fees:
            line.set_to_draft()
        self.write({'state': 'draft'})

    @api.multi
    def create_fee_for_fee_lines(self, student_ids, fee_structure_lines):
        for fee_line in fee_structure_lines:
            fee_line.create_fee_for_students(student_ids)

    def create_all_fees(self, student_ids=False, fee_structure_lines=False):
        if not student_ids:
            student_ids = self.student_ids
        if type(student_ids) is list:
            student_ids = self.env['ss.student'].browse(student_ids)
        if not fee_structure_lines:
            fee_structure_lines = self.fee_structure_lines
        if type(fee_structure_lines) is list:
            fee_structure_lines = self.env['ss.fee.type'].browse(fee_structure_lines)
        self.create_fee_for_fee_lines(student_ids, fee_structure_lines)

    def process_fees(self):
        self.create_all_fees()

    @api.multi
    def action_activate(self):
        (self.one_time_fees | self.recurring_fees).action_activate()
        self.process_fees()
        self.write({'state': 'active'})

    @api.multi
    def suspend(self):
        self.write({'state': 'inactive'})

    @api.multi
    def resume(self):
        fee_lines = (self.one_time_fees | self.recurring_fees).filtered(
            lambda s: not s.activated_once
        )
        self.create_fee_for_fee_lines(self.student_ids, fee_lines)
        self.write({'state': 'active'})

    @api.multi
    def generate_one_time_fees_manually(self):
        if not self.one_time_fees.filtered(lambda s: s.generation_type == 'one_time'):
            raise ValidationError('No one time fees found.Please add at least one fees to generate invoice')
        self.generate_invoice_for_one_time_fees(self.student_ids)


class FslExecutionLines(models.Model):
    _name = 'fsl.execution_date.lines'
    _rec_name = 'date'

    date = fields.Date()
    fsl_id = fields.Many2one('fee.structure.line')


class FeeStructureLine(models.Model):
    _name = 'fee.structure.line'
    _description = 'Fee Structure Line'

    name = fields.Char(string='Description', required=True)

    fee_structure_id = fields.Many2one('fee.structure', required=True)
    academic_year = fields.Many2one(related='fee_structure_id.academic_year')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id)
    fees_type = fields.Many2one('ss.fees.type', string='Fees Type', required=True)
    generation_type = fields.Selection(string="Generation Type", selection=[('one_time', 'One Time'),
                                                                            ('recurring', 'Recurring')])
    fees_amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')

    interval_number = fields.Integer(default=1, help="Repeat every x.")
    interval_type = fields.Selection([('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')],
                                     string='Interval Unit', default='months')

    nextcall = fields.Date(string='Recurrance Starting Date', required=True, default=fields.Date.today,
                               help="Next Date for the generation of fee for this Fees.")

    execution_date_lines = fields.One2many('fsl.execution_date.lines', 'fsl_id')

    payment_term = fields.Many2one('account.payment.term', string="Due Day(s)")
    is_active = fields.Boolean("Active", default=True)

    fee_ids = fields.One2many('ss.fee', 'fee_structure_line_id', readonly=True)

    activated_once = fields.Boolean()

    @api.onchange('fee_structure_id', 'fees_type')
    def set_name(self):
        self.name = '%s/%s' % (self.fee_structure_id.name or '', self.fees_type.name or '')

    def _prepare_fee_vals(self, student):
        return {
            'student_id': student.id,
            'partner_id': student.partner_id.id,
            'account_id': student.partner_id.with_context(
                force_company=self.company_id.id).property_account_receivable_id.id,
            'fee_type': self.fees_type.id,
            'fee_account_id': self.fees_type.account_id.id,
            'to_invoice': self.fees_type.to_invoice,
            'journal_id': self.fees_type.journal_id.id,
            'currency_id': self.currency_id.id,
            'payment_terms': self.payment_term.id,
            'amount': self.fees_amount,
            'created_from_fee_structure': True,
            'fee_structure_id': self.fee_structure_id.id,
            'fee_structure_line_id': self.id
        }

    def set_next_nextcall(self, nextcall):
        self.execution_date_lines.create({
            'fsl_id': self.id,
            'date': nextcall
        })
        nextcall = fields.Date.from_string(nextcall)
        nextcall += _intervalTypes[self.interval_type](self.interval_number)
        nextcall = fields.Date.to_string(nextcall)
        return nextcall

    def reset_nextcall(self):
        self.nextcall = fields.Date.today()

    def create_recurring_fees(self, students, fees_list):
        fee_o = self.env['ss.fee']
        this_month = fields.Date.today()[:-2] + '01'
        for date_line in self.execution_date_lines.filtered(lambda s: not fs(s.date) < fs(this_month)):
            for student in students:
                vals = self._prepare_fee_vals(student)
                vals.update(mature_date=date_line.date)
                fees_list.append(fee_o.create(vals).id)

    def create_fee(self, students, fees_list):
        fee_o = self.env['ss.fee']
        for student in students:
            fees_list.append(fee_o.create(self._prepare_fee_vals(student)).id)

    @api.one
    def action_activate(self):
        if self.generation_type == 'recurring':
            nextcall = self.nextcall
            while nextcall < self.academic_year.date_stop:
                nextcall = self.set_next_nextcall(nextcall)
        self.activated_once = True

    @api.multi
    def create_fee_for_students(self, student_ids):
        fees_list = []
        if type(student_ids) is list:
            student_ids = self.env['ss.student'].browse(student_ids)
        if self.generation_type == 'one_time':
            self.create_fee(student_ids, fees_list)
        else:
            self.create_recurring_fees(student_ids, fees_list)
        self.env['ss.fee'].browse(fees_list).validate()

    @api.multi
    def set_to_draft(self):
        self.fee_ids.unlink()
        self.execution_date_lines.unlink()


