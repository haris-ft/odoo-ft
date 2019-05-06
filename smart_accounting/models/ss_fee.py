import json
from odoo import fields, api, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero
fs = fields.Date.from_string
ts = fields.Date.to_string

DRAFT_READONLY = {'draft': [('readonly', False)]}


class SsFeesType(models.Model):
    """ This will maintain the fees head details """
    _name = 'ss.fees.type'
    _description = "Fees Types"
    _rec_name = 'name'

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Char(string='Description')
    company_id = fields.Many2one('res.company', 'Institution', default=lambda self: self.env.user.company_id.id,
                                 required=True, index=1)
    fees_type = fields.Selection(string="Type", selection=[('one_time', 'One Time'), ('recurring', 'Recurring'), ],
                                 required=True, default='one_time')
    to_invoice = fields.Boolean('To Invoice', required=True)
    account_id = fields.Many2one("account.account", string="Account")

    sequence_id = fields.Many2one('ir.sequence', string='Specific Sequence')
    journal_id = fields.Many2one('account.journal', string='Specific Journal')

    @api.constrains('code', 'name')
    def _check_fee_type(self):
        if self.name and self.code:
            existing_line = self.env['ss.fees.type'].search([('name', '=', self.name), ('id', '!=', self.id)])
            if existing_line:
                raise ValidationError('Fees Type and Code Must be Unique')


class SsFee(models.Model):
    _name = 'ss.fee'
    _order = 'state asc, mature_date asc'

    @api.one
    @api.depends('student_id')
    def get_student_spec(self):
        if self.student_id:
            self.update({
                'partner_id': self.student_id.partner_id.id,
                'course_id': self.student_id.course_id.id,
                'standard_id': self.student_id.standard_id.id,
                'division_id': self.student_id.division_id.id,
                'fee_structure_id': self.student_id.fee_structure_id.id,
            })

    @api.one
    @api.depends('partner_id')
    def get_rec_account_id(self):
        if self.partner_id:
            p = self.partner_id.with_context(force_company=self.company_id.id)
            self.account_id = p.property_account_receivable_id

    @api.one
    @api.depends('state', 'currency_id', 'move_id.line_ids.amount_residual', 'move_id.line_ids.currency_id',
                 'advance_move_lines.amount_residual')
    def _compute_residual(self):
        digits_rounding_precision = self.currency_id.rounding
        if not self.move_id:
            if self.advance_move_lines:
                self.residual = self.amount + sum(self.advance_move_lines.mapped('amount_residual'))
                if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
                    self.reconciled = True
                else:
                    self.reconciled = False
                return
            self.residual = self.amount
            return
        residual = 0.0
        for line in self.sudo().move_id.line_ids:
            if line.account_id == self.account_id:
                if line.currency_id == self.currency_id:
                    residual += line.amount_residual_currency if line.currency_id else line.amount_residual
                else:
                    from_currency = (line.currency_id and line.currency_id.with_context(
                        date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
                    residual += from_currency.compute(line.amount_residual, self.currency_id)
        self.residual = abs(residual)

        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
        else:
            self.reconciled = False

    @api.one
    @api.depends('invoice_id.payment_ids', 'fee_payment_ids')
    def get_payment_ids(self):
        self.payment_ids = self.fee_payment_ids | self.invoice_id.payment_ids

    @api.depends('mature_date', 'fee_type', 'fee_structure_id', 'fee_structure_id.name')
    def _get_ref_name(self):
        for rec in self:
            rec.ref_name = '%s-%s-%s' % (fs(rec.mature_date).strftime('%B'), rec.fee_type.name,
                                         rec.fee_structure_id and rec.fee_structure_id.name or '')

    name = fields.Char('Reference', default='New', required=True, readonly=True)
    ref_name = fields.Char(string='Fee Name', compute='_get_ref_name', store=True)
    description = fields.Char('Description', readonly=True, states=DRAFT_READONLY)
    mature_date = fields.Date('Mature Date', required=True, default=fields.Date.today, readonly=True,
                              states=DRAFT_READONLY)
    partner_type = fields.Selection([('student', 'Student'), ('external', 'External')], default='student', required=True)

    student_id = fields.Many2one('ss.student', readonly=True, states=DRAFT_READONLY)
    partner_id = fields.Many2one('res.partner', required=True, readonly=True, states=DRAFT_READONLY)

    academic_year = fields.Many2one('academic.year', required=True, readonly=True, states=DRAFT_READONLY,
                                    default=lambda self: self.env.user.company_id.current_academic_year.id)

    company_id = fields.Many2one('res.company', required=True, readonly=True,
                                 default=lambda s: s.env.user.company_id.id)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True, states=DRAFT_READONLY,
                                  default=lambda s: s.env.user.company_id.currency_id.id)

    course_id = fields.Many2one('ss.course', readonly=True, compute='get_student_spec', store=True)
    standard_id = fields.Many2one('ss.standard', readonly=True, compute='get_student_spec', store=True)
    division_id = fields.Many2one('ss.division', readonly=True, compute='get_student_spec', store=True)

    state = fields.Selection([('draft', 'Draft'), ('validated', 'Validated'), ('advanced', 'Advanced'),
                              ('open', 'To Pay'), ('paid', 'Paid')], default='draft', required=True, readonly=True)

    fee_type = fields.Many2one('ss.fees.type', required=True, readonly=True, states=DRAFT_READONLY)

    created_from_fee_structure = fields.Boolean('Created from Fee Structure ?', readonly=True)
    fee_structure_id = fields.Many2one('fee.structure', readonly=True)
    fee_structure_line_id = fields.Many2one('fee.structure.line', readonly=True)

    fee_account_id = fields.Many2one('account.account', string='Fees Account', required=True)
    account_id = fields.Many2one('account.account', string='Account', compute='get_rec_account_id', store=True,
                                 domain=[('deprecated', '=', False)])
    to_invoice = fields.Boolean('To Invoice', readonly=True, states=DRAFT_READONLY)
    invoice_date = fields.Date('Invoice Date', readonly=True, states=DRAFT_READONLY)
    payment_terms = fields.Many2one('account.payment.term', string="Payment Term", readonly=True, states=DRAFT_READONLY)
    journal_id = fields.Many2one('account.journal', string='Journal', readonly=True, states=DRAFT_READONLY)

    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    invoice_id = fields.Many2one('account.invoice', readonly=True)

    fee_payment_ids = fields.Many2many('account.payment', 'ss_fee_account_payment_rel', 'fee_id', 'payment_id')
    payment_ids = fields.Many2many('account.payment', compute='get_payment_ids', readonly=True)

    reconciled = fields.Boolean(string='Paid/Reconciled', store=True, readonly=True, compute='_compute_residual')

    amount = fields.Monetary('Total Amount', required=True, readonly=True, states=DRAFT_READONLY)

    residual = fields.Monetary(string='Amount Due', compute='_compute_residual', store=True,
                               help="Remaining amount due.")
    advance_move_lines = fields.Many2many('account.move.line', 'ss_fee_advanced_move_lines')

    @api.onchange('fee_type')
    def onchange_fee_type(self):
        if self.fee_type:
            self.fee_account_id = self.fee_type.account_id.id
            self.to_invoice = self.fee_type.to_invoice
            if self.fee_type.journal_id:
                self.journal_id = self.fee_type.journal_id.id

    @api.multi
    def create_move(self):
        if self.journal_id:
            journal = self.journal_id
        else:
            domain = [
                ('type', '=', 'sale'),
                ('company_id', '=', self.company_id.id),
            ]
            journal = self.env['account.journal'].search(domain, limit=1)
        debit_vals = {
            'name': self.name,
            'debit': abs(self.amount),
            'credit': 0.0,
            'partner_id': self.student_id.partner_id.id,
            'account_id': self.account_id.id,
        }
        credit_vals = {
            'name': self.name,
            'debit': 0.0,
            'credit': abs(self.amount),
            'account_id': self.fee_account_id.id,
            'partner_id': self.student_id.partner_id.id
        }
        vals = {
            'journal_id': journal.id,
            'date': self.mature_date,
            'state': 'draft',
            'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)]
        }
        move = self.env['account.move'].create(vals)
        move.post()
        return move.id

    def _prepare_invoice(self):
        invoice_vals = {
            'number': self.name,
            'partner_id': self.partner_id.id,
            'date_invoice': self.invoice_date or fields.Date.today(),
            'payment_term_id': self.payment_terms,
            'name': self.description,
            'fee_id': self.id
        }
        if self.journal_id:
            invoice_vals.update(journal_id=self.journal_id.id)
        return invoice_vals

    def _prepare_invoice_line(self, invoice_id):
        inv_line_vals = {
            'invoice_id': invoice_id,
            'name': '%s/%s' % (self.fee_type.name, self.student_id.name),
            'account_id': self.fee_type.account_id.id,
            'price_unit': self.amount
        }
        return inv_line_vals

    def create_invoice(self):
        if not self.partner_id:
            raise UserError('You cannot generate an Invoice without a Partner.')
        self.invoice_id = self.env['account.invoice'].create(self._prepare_invoice())
        self.env['account.invoice.line'].create(self._prepare_invoice_line(self.invoice_id.id))

    @api.multi
    def action_fee_payment(self):
        return {
            'name': _("Register Payment"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('smart_accounting.wizard_fee_account_payment').id,
            'view_type': 'form',
            'res_model': 'account.payment',
            'context': {
                'default_fee_ids': [(4, self.id, None)],
                'default_student_id': self.student_id.id,
                'default_partner_id': self.partner_id.id
            },
            'target': 'new',
        }

    @api.multi
    def action_view_invoice(self):
        if self.invoice_id:
            return {
                'name': _("Invoice for Fee"),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'account.invoice',
                'res_id': self.invoice_id.id
            }

    @api.multi
    def action_view_payments(self):
        if self.payment_ids:
            return {
                'name': _("Payments for Fee"),
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'view_type': 'form',
                'res_model': 'account.payment',
                'domain': [('id', 'in', self.fee_payment_ids.ids)]
            }

    @api.multi
    def force_open(self):
        self.action_fee_open()

    @api.multi
    def action_fee_open(self):
        for fee in self:
            if fee.to_invoice:
                fee.create_invoice()
                fee.invoice_id.action_invoice_open()
                move_id = fee.invoice_id.move_id.id
            else:
                move_id = fee.create_move()
            fee.write({
                'state': 'open',
                'move_id': move_id
            })

    @api.multi
    def action_fee_paid(self):
        for fee in self:
            fee.write({'state': 'paid'})

    @api.multi
    def validate(self):
        for fee in self:
            fee.state = 'validated'
            if (not fee.name) or fee.name == 'New':
                if fee.fee_type.sequence_id:
                    fee.name = fee.fee_type.sequence_id.next_by_id()
                else:
                    fee.name = fee.env['ir.sequence'].next_by_code('ss.fee')
            fee.to_invoice = fee.fee_type.to_invoice
            if fee.mature_date <= fields.Date.today():
                fee.action_fee_open()

    @api.multi
    def _write(self, vals):
        pre_not_reconciled = self.filtered(lambda fee: not fee.reconciled)
        pre_reconciled = self - pre_not_reconciled
        res = super(SsFee, self)._write(vals)
        reconciled = self.filtered(lambda fee: fee.reconciled)
        not_reconciled = self - reconciled
        (reconciled & pre_reconciled).filtered(lambda fee: fee.state == 'open').action_fee_paid()
        (not_reconciled & pre_not_reconciled).filtered(lambda fee: fee.state == 'paid').action_fee_open()
        return res

    @api.multi
    def register_payment(self, payment_line, writeoff_acc_id=False, writeoff_journal_id=False):
        line_to_reconcile = self.env['account.move.line']
        for fee in self:
            line_to_reconcile += fee.move_id.line_ids.filtered(lambda r: not r.reconciled and r.account_id.internal_type in ('payable', 'receivable'))
        return (line_to_reconcile + payment_line).reconcile(writeoff_acc_id, writeoff_journal_id)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    fee_id = fields.Many2one('ss.fee')