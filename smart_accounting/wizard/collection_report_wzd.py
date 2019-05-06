from odoo import models, fields, api
from datetime import date, datetime

class CollectionReport(models.TransientModel):
    _name = 'collection.wizard'

    type = fields.Selection([('period','Period'),('daily','Daily')], string="Type", required=True, default="period")
    from_date = fields.Date(string="From date", default=fields.Date.today(), required=True)
    to_date = fields.Date(string="To date", default=fields.Date.today(),  required=True)
    date = fields.Date(string="Date", default=fields.Date.today(),  required=True)
    standard = fields.Many2many('ss.standard', string="Standard")
    division = fields.Many2many('ss.division', string="Division")
    journal_type = fields.Many2many('account.journal', string='Journal Type')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.user.company_id.id)

    @api.multi
    def generate_report(self):
        return self.env.ref('smart_accounting.fees_collection_action').report_action(self, data=self.read([])[0])
