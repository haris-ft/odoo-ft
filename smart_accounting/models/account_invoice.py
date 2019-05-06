from odoo import api, fields, models
import odoo.addons.decimal_precision as dp


class AccountInvoice(models.Model):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    course_id = fields.Many2one(related='partner_id.course_id', readonly=True)
    standard_id = fields.Many2one(related='partner_id.standard_id', readonly=True, string="Standard")
    division_id = fields.Many2one(related='partner_id.division_id', readonly=True, string="Division")
    admission_no = fields.Char(related='partner_id.admission_no', readonly=True, string="Admission Number")

    academic_year = fields.Many2one('academic.year', string="Academic Year",
                                    default=lambda self: self.env.user.company_id.current_academic_year.id,
                                    required=True)


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
                 'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
                 'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        if self.discount_type == 'a':
            price = self.price_unit - (self.discount or 0.0)
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
        if self.invoice_id.currency_id and self.invoice_id.company_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.with_context(date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign

    discount_type = fields.Selection([('p','Percentage'),('a','Amount')], string="Discount Type", default='p')
    discount = fields.Float(string='Discount', digits=dp.get_precision('Discount'),
        default=0.0)

    student_id = fields.Many2one('ss.student', string='Student')
    fee_structure_id = fields.Many2one('fee.structure', string='Fee Structure')
    fee_structure_line = fields.Many2one('fee.structure.line', string='Fee Structure Line')
    # one_time_line = fields.Many2one('one.time.fees', string='One Time Fee', )
    # recurring_line = fields.Many2one('recurring.fees', string='Recurring Fee',)
    fees_type = fields.Selection(string="Type", selection=[('one_time', 'One Time'), ('recurring', 'Recurring'), ],
                                 default='one_time')

