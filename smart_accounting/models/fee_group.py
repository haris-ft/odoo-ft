from odoo import fields, models, api


class FeeGroup(models.Model):
    _name = 'fee.group'
    _rec_name = 'name'
    _description = 'Model to manage fee groups'

    name = fields.Char(string='Name', required=True)
    description = fields.Char('Description')
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.user.company_id.id,
                                 required=True)
    group_type = fields.Selection(string="Type", selection=[('standard_wise', 'Standard Wise'),
                                                            ('division_wise', 'Division Wise'),
                                                            ('student_wise', 'Student Wise'), ], required=True,
                                  default='standard_wise')
    standard_line = fields.Many2many('ss.standard')
    division_line = fields.Many2many('ss.division')
    fee_structure_ids = fields.One2many('fee.structure', 'fee_group')
    student_ids = fields.One2many('ss.student', 'fee_group')
    standard_id = fields.Many2one('ss.standard', string='Standard')
    division_id = fields.Many2one('ss.division', string='Division')

    @api.model
    def create(self, vals):
        if 'group_type' in vals:
            if vals['group_type'] == 'standard_wise':
                vals.update({
                    'division_line': False,
                })
            elif vals['group_type'] == 'student_wise':
                vals.update({
                    'division_line': False,
                    'standard_line': False
                })
            elif vals['group_type'] == 'division_wise':
                vals.update({
                    'standard_line': False
                })
        return super(FeeGroup, self).create(vals)

    @api.multi
    def write(self, vals):
        if 'group_type' in vals:
            if self.group_type == 'standard_wise':
                vals.update({'standard_line': [(5,)]})
            elif self.group_type == 'division_wise':
                vals.update({'division_line': [(5,)]})
        return super(FeeGroup, self).write(vals)

    @api.onchange('group_type')
    def onchange_group_type(self):
        if self.group_type:
            if self.group_type == 'standard_wise':
                self.division_line = False
            elif self.group_type == 'student_wise':
                self.standard_line = False
                self.division_line = False
            if self.group_type == 'division_wise':
                self.standard_line = False

    @api.onchange('standard_id')
    def onchange_standard(self):
        self.division_id = False
