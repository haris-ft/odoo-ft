from odoo import fields, api, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fee_group = fields.Many2one('fee.group', string='Fee Group')
    fee_structure_id = fields.Many2one('fee.structure', string='Fee Structure')
    fee_invoice_lines = fields.One2many('account.invoice.line', 'student_id', )
    fee_structure_lines = fields.One2many('student.fee.structure.line', 'student_id')


class SsStudent(models.Model):
    _inherit = 'ss.student'

    fees_creation_initiated = fields.Boolean('Fees Created Once')

    @api.model
    def get_default_fee_structure_group(self, academic_year_id, standard_id, division_id):
        division_wise_fee_group = self.env['fee.group'].search([('group_type', '=', 'division_wise'),
                                                                ('division_line', '=', division_id),
                                                                ('fee_structure_ids', '!=', False)], )
        standard_wise_fee_group = self.env['fee.group'].search([('group_type', '=', 'standard_wise'),
                                                                ('standard_line', '=', standard_id),
                                                                ('fee_structure_ids', '!=', False)])
        student_wise_fee_group = self.env['fee.group'].search([('group_type', '=', 'student_wise'),
                                                               '|', ('standard_id', '=', standard_id),
                                                               ('standard_id', '=', False), '|',
                                                               ('division_id', '=', division_id),
                                                               ('division_id', '=', False),
                                                               ('fee_structure_ids', '!=', False)
                                                               ])
        fee_ids = division_wise_fee_group.ids + standard_wise_fee_group.ids + student_wise_fee_group.ids
        if division_wise_fee_group:
            fee_group = division_wise_fee_group[0]
        elif standard_wise_fee_group:
            fee_group = standard_wise_fee_group[0]
        else:
            fee_group = student_wise_fee_group.filtered(lambda s: s.division_id.id == division_id)
            if fee_group:
                fee_group = fee_group[0]
            else:
                fee_group = student_wise_fee_group.filtered(lambda s: s.standard_id.id == standard_id)
                if not fee_group:
                    fee_group = student_wise_fee_group.filtered(lambda s: not s.standard_id.id and
                                                                          not s.division_id.id)

        fee_structure_id = fee_group.fee_structure_ids.filtered(lambda s: s.academic_year.id == academic_year_id)
        return fee_group, fee_structure_id, fee_ids

    @api.onchange('standard_id', 'division_id')
    def set_default_fees_structure_group(self):
        if self.academic_year and self.standard_id and self.division_id:
            self.fee_group, self.fee_structure_id, x = self.get_default_fee_structure_group(
                self.academic_year.id, self.standard_id.id, self.division_id.id
            )

    @api.multi
    def create_all_fees(self):
        self.fee_structure_id.create_all_fees(self)
        self.fees_creation_initiated = True

    @api.multi
    def view_fees_of_student(self):
        return {
            'name': _("Fees of Student: %s" % self.name),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'ss.fee',
            'domain': [('student_id', '=', self.id)]
        }


class StudentFeeStructureLine(models.Model):
    _name = 'student.fee.structure.line'

    student_id = fields.Many2one('ss.student', string='Student')
    fee_structure_line = fields.Many2one('fee.structure.line', string='Fee Structure Line')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id)
    price_unit = fields.Monetary('Price', currency_field='currency_id')
    discount_type = fields.Selection(string="Discount Type", selection=[('amount', 'Amount'),
                                                                        ('percentage', 'Percentage')])
    discount = fields.Float(string="Discount")
    amount = fields.Monetary(string='Amount', currency_field='currency_id')


