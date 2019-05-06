from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    default_fee_advance_journal_id = fields.Many2one('account.journal')
    default_advance_account_id = fields.Many2one('account.account')

    default_discount_journal_id = fields.Many2one('account.journal')
    default_discount_account_id = fields.Many2one('account.account')

    default_round_off_account_id = fields.Many2one('account.account')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_fee_advance_journal_id = fields.Many2one(related='company_id.default_fee_advance_journal_id')
    default_advance_account_id = fields.Many2one(related='company_id.default_advance_account_id')

    default_discount_journal_id = fields.Many2one(related='company_id.default_discount_journal_id')
    default_discount_account_id = fields.Many2one(related='company_id.default_discount_account_id')

    default_round_off_account_id = fields.Many2one(related='company_id.default_round_off_account_id')

    @api.onchange('default_fee_advance_journal_id')
    def set_default_advance_account_id(self):
        if self.default_fee_advance_journal_id and self.default_fee_advance_journal_id.default_credit_account_id:
            self.default_advance_account_id = self.default_fee_advance_journal_id.default_credit_account_id

    @api.onchange('default_discount_journal_id')
    def set_default_advance_account_id(self):
        if self.default_discount_journal_id and self.default_discount_journal_id.default_credit_account_id:
            self.default_discount_account_id = self.default_discount_journal_id.default_credit_account_id

    @api.model
    def create(self, vals):
        if vals.get('default_advance_account_id') and not self.env['account.account'].browse(
                vals.get('default_advance_account_id')).reconcile:
            raise ValidationError('Default Advance Account should have Allow Reconcilation Enabled.')
        return super(ResConfigSettings, self).create(vals)
