from odoo import api, fields, models, _
from odoo.exceptions import UserError
DRAFT_READONLY = {'draft': [('readonly', False)]}


class SsFeePayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    def default_get(self, fields):
        rec = super(SsFeePayment, self).default_get(fields)
        rec['payment_type'] = 'inbound'
        rec['partner_type'] = 'customer'
        if rec.get('fee_ids') and len(rec['fee_ids'][0]) > 1:
            fee_ids = self.env['ss.fee'].browse(rec['fee_ids'][0][2])
            if len(fee_ids.mapped('student_id')) > 1:
                raise UserError('You have selected Fees of different Students.')
            rec['student_id'] = fee_ids.mapped('student_id').id
        return rec

    @api.one
    @api.depends('fee_ids')
    def get_has_fees(self):
        self.has_fees = bool(self.fee_ids)

    @api.one
    @api.depends('amount', 'currency_id', 'payment_lines.current_pay_amount', 'payment_lines.discounted_residual')
    def _compute_fee_payment_difference(self):
        if len(self.payment_lines) == 0 or not self.amount:
            return
        difference = self.amount - sum(self.payment_lines.filtered(lambda s: s.fee_id.state == 'open')
                                       .mapped(
            lambda s: s.residual - (s.residual * (s.discount/100) if s.discount_mode == 'percent' else s.discount)))
        self.fee_payment_difference = difference if difference > 0.0 else 0.0

    @api.one
    @api.depends('student_id')
    def get_student_spec(self):
        for record in self:
            record.update({
                'course_id': record.student_id.course_id.id,
                'standard_id': record.student_id.standard_id.id,
                'division_id': record.student_id.division_id.id
            })

    @api.one
    @api.depends('payment_lines', 'payment_lines.discounted_residual', 'payment_lines.state')
    def get_total_amounts(self):
        if self.payment_lines:
            self.total_due_amount = sum(self.payment_lines.filtered(lambda s: s.fee_id.state == 'open').mapped('discounted_residual'))
            self.total_advance_amount = sum(self.payment_lines.filtered(lambda s: s.fee_id.state == 'validated')
                                            .mapped('discounted_residual'))

    @api.one
    @api.depends('payment_lines', 'payment_lines.current_pay_amount')
    def get_total_payment_specs(self):
        self.total_due_receivable = sum(self.payment_lines.filtered(lambda s: s.fee_id.state == 'open')
                                        .mapped('current_pay_amount'))
        self.total_advance_receivable = sum(self.payment_lines.filtered(lambda s: s.fee_id.state == 'validated')
                                            .mapped('current_pay_amount'))

    student_id = fields.Many2one('ss.student', readonly=True, states=DRAFT_READONLY)

    course_id = fields.Many2one('ss.course', compute='get_student_spec', store=True)
    standard_id = fields.Many2one('ss.standard', compute='get_student_spec', store=True)
    division_id = fields.Many2one('ss.division', compute='get_student_spec', store=True)

    without_student = fields.Boolean('Payment without Student ?')
    applied_for = fields.Selection([('all', 'All Fee Types'), ('fee_type', 'Fee Types')],
                                   default='all', required=True, readonly=True, states=DRAFT_READONLY)

    total_due_amount = fields.Monetary(string='Due Total', compute='get_total_amounts')
    total_advance_amount = fields.Monetary(string='Advance-able Total', compute='get_total_amounts')

    fee_type_ids = fields.Many2many('ss.fees.type')

    partner_fee_structure_id = fields.Many2one(related='partner_id.fee_structure_id', readonly=True)

    payment_lines = fields.One2many('account.payment.line', 'fee_payment_id', readonly=True, states=DRAFT_READONLY)

    # Just for View Handling
    payment_lines_manual_disc = fields.One2many(related='payment_lines')
    payment_lines_auto_disc = fields.One2many(related='payment_lines')

    fee_payment_difference = fields.Monetary(compute='_compute_fee_payment_difference', readonly=True, store=True)
    fee_payment_difference_handling = fields.Selection([
        ('round_off', 'Round Off'), ('advance', 'Add as Advance Amount')]
        , default='round_off', string="Payment Difference As", copy=False)

    round_off_account = fields.Many2one('account.account', readonly=True, states=DRAFT_READONLY,
                                        default=lambda s: s.env.user.company_id.default_round_off_account_id.id)

    fee_advance_journal_id = fields.Many2one('account.journal', readonly=True, states=DRAFT_READONLY,
                                             default=lambda s: s.env.user.company_id.default_fee_advance_journal_id.id)
    fee_advance_account_id = fields.Many2one('account.account', readonly=True, states=DRAFT_READONLY,
                                             default=lambda s: s.env.user.company_id.default_advance_account_id.id)

    with_discount = fields.Boolean('Enable Discount', readonly=True, states=DRAFT_READONLY)
    discount_method = fields.Selection([('manual', 'Apply Discount Manually Line by Line'),
                                        ('auto', 'Apply Discount Automatically by Rules')],
                                       default='manual', readonly=True, states=DRAFT_READONLY)

    discount_mode = fields.Selection([('value', 'Value'), ('percent', '%')], default='percent', readonly=True,
                                     states=DRAFT_READONLY)

    discount_distribution = fields.Selection([('all', 'All'), ('fee_type', 'Fee Types')], default='all', readonly=True,
                                             states=DRAFT_READONLY)
    discount_fee_type_ids = fields.Many2many('ss.fees.type', readonly=True, states=DRAFT_READONLY)

    discount = fields.Float('Discount', readonly=True, states=DRAFT_READONLY)

    discount_account_id = fields.Many2one('account.account', readonly=True, states=DRAFT_READONLY,
                                          default=lambda s: s.env.user.company_id.default_discount_account_id.id)
    discount_journal_id = fields.Many2one('account.journal', readonly=True, states=DRAFT_READONLY,
                                          default=lambda s: s.env.user.company_id.default_discount_journal_id.id)
    discount_move = fields.Many2one('account.move')

    has_fees = fields.Boolean(compute='get_has_fees')
    fee_ids = fields.Many2many('ss.fee', 'ss_fee_account_payment_rel', 'payment_id', 'fee_id')

    total_due_receivable = fields.Monetary('Net Due Receivable', compute='get_total_payment_specs', store=True)
    total_advance_receivable = fields.Monetary('Net Adv Receivable', compute='get_total_payment_specs', store=True)

    pay_all = fields.Boolean('Pay All')

    @api.onchange('student_id', 'applied_for', 'fee_type_ids')
    def set_partner_fee_domains_and_payment_lines(self):
        fee_type_ids = []
        if not self.student_id:
            ids = []
            self.payment_lines = [(5,)]
            self.partner_id = False
        else:
            self.partner_id = self.student_id.partner_id
            ids = self.student_id.fee_structure_id.mapped('fee_structure_lines.fees_type').ids

            fee_type_ids = ids if self.applied_for == 'all' else self.fee_type_ids.ids
            if self.fee_ids:
                fee_ids = self.fee_ids
            else:
                fee_ids = self.get_applicable_fee_ids(
                    self.student_id, with_fee_type=(self.applied_for == 'fee_type'), fee_type_ids=fee_type_ids)

            self.payment_lines = [(0, 0, {
                'fee_id': i.id,
                'current_pay_amount': i.residual if i.state == 'open' else 0.0
            }) for i in fee_ids]
            self.with_discount = False

        return {'domain': {
            'fee_type_ids': [('id', 'in', ids)],
            'applicable_fee_ids': [('student_id', '=', self.student_id.id),
                                   ('fees_type', 'in', fee_type_ids),
                                   ('state', 'in', ['validated', 'open'])]
        }}

    def get_applicable_fee_ids(self, student, with_fee_type=False, fee_type_ids=False):
        domain = [('student_id', '=', student.id), ('state', 'in', ['validated', 'open'])]
        if with_fee_type:
            fee_type_ids = [fee_type_ids] if type(fee_type_ids) is int else fee_type_ids
            domain.append(('fee_type', 'in', fee_type_ids))
        return self.env['ss.fee'].search(domain)

    @api.onchange('payment_lines', 'fee_payment_difference_handling', 'fee_ids')
    def set_amount(self):
        if self.fee_ids and not self.payment_lines:
            self.payment_lines = [(0, 0, {
                'fee_id': i.id,
                'current_pay_amount': i.residual if i.state == 'open' else 0.0
            }) for i in self.fee_ids]
        if self.amount > self.total_due_amount:
            if self.fee_payment_difference > 0.0 and self.fee_payment_difference_handling == 'advance':
                amount = sum(self.payment_lines.mapped('current_pay_amount'))
            else:
                amount = self.amount
        else:
            amount = sum(self.payment_lines.filtered(lambda s: s.fee_id.state == 'open').mapped('current_pay_amount'))
        return {'value': {'amount': amount}}

    @api.onchange('with_discount', 'discount_method', 'discount_mode', 'discount_distribution', 'discount_fee_type_ids',
                  'discount')
    def apply_discount(self):
        if not self.with_discount:
            self.payment_lines.update({'discount_mode': '', 'discount': 0.0})
            return
        if self.discount_method == 'auto':
            disc_val = {'discount_mode': self.discount_mode, 'discount': self.discount}
            if self.discount_distribution == 'all':
                self.payment_lines.update(disc_val)
            else:
                self.payment_lines.filtered(lambda s: s.fee_id.fee_type.id in self.discount_fee_type_ids.ids).update(disc_val)
        else:
            self.payment_lines.update({'discount_mode': '', 'discount': 0.0})
        total = 0.0
        for line in self.payment_lines:
            discount_value = line.residual * (line.discount/100) if line.discount_mode == 'percent' else line.discount
            total += line.current_pay_amount - discount_value
        self.amount = total

    @api.onchange('pay_all')
    def pay_all_lines(self):
        if self.pay_all:
            self.amount = sum(self.payment_lines.mapped('discounted_residual'))
            self.fee_payment_difference_handling = 'advance'

    @api.onchange('discount_method')
    def set_all_payment_lines_discount_method(self):
        self.payment_lines.update({'discount_method': self.discount_method})

    def get_advance_fee_ids(self, student, with_fee_type=False, fee_type_ids=False):
        domain = [('student_id', '=', student.id), ('state', 'in', ['validated'])]
        if with_fee_type:
            fee_type_ids = [fee_type_ids] if type(fee_type_ids) is int else fee_type_ids
            domain.append(('fee_type', 'in', fee_type_ids))
        return self.env['ss.fee'].search(domain)

    @api.onchange('fee_advance_journal_id')
    def onchange_fee_advance_journal_id(self):
        if self.fee_advance_journal_id:
            if not self.fee_advance_journal_id.default_credit_account_id:
                raise UserError('Please set a Default Credit Account for this Journal')
            else:
                self.fee_advance_account_id = self.fee_advance_journal_id.default_credit_account_id

    @api.onchange('fee_payment_difference')
    def reset_fee_advance_handling(self):
        if self.fee_payment_difference <= 0.0:
            self.fee_payment_difference_handling = 'round_off'

    @api.onchange('amount', 'currency_id', 'fee_payment_difference_handling')
    def onchange_amount(self):
        if not self.journal_id:
            journal_domain = [('type', 'in', ['bank', 'cash'])]
            self.journal_id = self.env['account.journal'].search(journal_domain, limit=1).id
        amount = self.amount
        self.payment_lines.update({'current_pay_amount': 0.0})
        if self.fee_payment_difference > 0.0 and self.fee_payment_difference_handling == 'advance':
            lines = self.payment_lines
        else:
            lines = self.payment_lines.filtered(lambda s: s.fee_id.state == 'open')
        for line in lines:
            line.current_pay_amount = line.discounted_residual if amount >= line.discounted_residual else amount
            amount -= line.current_pay_amount
        return {}

    @api.multi
    def button_journal_entries(self):
        res = super(SsFeePayment, self).button_journal_entries()
        res['domain'].append(('account_id', '!=', self.env.user.company_id.transfer_account_id.id))
        return res

    @api.multi
    def button_fees(self):
        return {
            'name': _("Fee List of Payment: %s" % self.name),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'ss.fee',
            'domain': [('id', 'in', self.fee_ids.ids)]
        }

    def _get_discount_move_vals(self):
        journal = self.discount_journal_id
        if not journal.sequence_id:
            raise UserError(_('Configuration Error !'),
                            _('The journal %s does not have a sequence, please specify one.') % journal.name)
        if not journal.sequence_id.active:
            raise UserError(_('Configuration Error !'), _('The sequence of journal %s is deactivated.') % journal.name)
        name = self.move_name or journal.with_context(ir_sequence_date=self.payment_date).sequence_id.next_by_id()
        return {
            'name': name,
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }

    def _get_discount_move_line_vals(self, move):
        return {
            'move_id': move.id,
            'journal_id': self.discount_journal_id.id
        }

    def _create_payment_entry(self, amount):
        if not self.student_id:
            move = super(SsFeePayment, self)._create_payment_entry(amount)
            to_reconcile = move.line_ids.filtered(
                lambda s: not s.reconciled and s.account_id.internal_type in ('receivable', 'payable'))
            if to_reconcile:
                self.payment_lines.mapped('fee_id').register_payment(to_reconcile)
            return move
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)

        debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(amount, self.currency_id, self.company_id.currency_id, False)

        move = self.env['account.move'].create(self._get_move_vals())
        to_reconcile_due_amls_dict = {}
        to_create_discount_amls = []
        to_reconcile_discount_aml = self.env['account.move.line']
        total_discount = 0.0
        for line in self.payment_lines.filtered(lambda s: (s.current_pay_amount > 0.0 or s.fee_id.residual == s.discount_value)):
            if line.state == 'open':
                counterpart_aml_dict = self._get_shared_move_line_vals(debit, line.current_pay_amount + line.discount_value, amount_currency, move.id, False)
                counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
                counterpart_aml_dict.update({
                    'name': 'Fee Due Payment (%s)' % line.name,
                    'currency_id': currency_id
                })
                counterpart_aml = aml_obj.create(counterpart_aml_dict)
                to_reconcile_due_amls_dict.update({line.id: counterpart_aml.id})
            if line.state == 'validated':
                counterpart_aml_dict = self._get_shared_move_line_vals(debit,  line.current_pay_amount + line.discount_value, amount_currency, move.id, False)
                counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
                counterpart_aml_dict.update({
                    'name': 'Fee Advance Payment (%s)' % line.name,
                    'account_id': self.fee_advance_account_id.id,
                    'currency_id': currency_id
                })
                counterpart_aml = aml_obj.create(counterpart_aml_dict)
                line.advance_move_lines |= counterpart_aml
            if line.discount_value:
                counterpart_aml_dict = self._get_shared_move_line_vals(line.discount_value, debit, amount_currency,
                                                                       move.id, False)
                counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
                counterpart_aml_dict.update({
                    'name': 'Fee Discount (%s)' % line.name,
                    'account_id': self.discount_account_id.id,
                    'currency_id': currency_id
                })
                if self.discount_journal_id:
                    total_discount += line.discount_value
                    to_create_discount_amls.append(counterpart_aml_dict)
                else:
                    aml_obj.create(counterpart_aml_dict)

        if self.fee_payment_difference > 0.0 and self.fee_payment_difference_handling == 'round_off':
            counterpart_aml_dict = self._get_shared_move_line_vals(debit, self.fee_payment_difference, amount_currency, move.id, False)
            counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
            counterpart_aml_dict.update({
                'name': 'Round-Off',
                'account_id': self.round_off_account.id,
                'currency_id': currency_id
            })
            aml_obj.create(counterpart_aml_dict)

        if not self.currency_id.is_zero(self.amount):
            if not self.currency_id != self.company_id.currency_id:
                amount_currency = 0
            liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
            liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
            aml_obj.create(liquidity_aml_dict)

        if self.discount_journal_id and to_create_discount_amls and total_discount > 0.0:
            discount_transfer_aml_dict = self._get_shared_move_line_vals(total_discount, debit, amount_currency,
                                                                   move.id, False)
            discount_transfer_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
            discount_transfer_aml_dict.update({
                'name': 'Fee Discount (Transfer)',
                'account_id': self.env.user.company_id.transfer_account_id.id,
                'currency_id': currency_id
            })
            to_reconcile_discount_aml = aml_obj.create(discount_transfer_aml_dict)

        if self.discount_journal_id and to_create_discount_amls:
            move_vals = self._get_discount_move_vals()
            self.discount_move = self.env['account.move'].create(move_vals)
            for vals in to_create_discount_amls:
                vals.update(self._get_discount_move_line_vals(self.discount_move))
                aml_obj.create(vals)

            discount_transfer_aml_dict = self._get_shared_move_line_vals(debit, total_discount, amount_currency,
                                                                         self.discount_move.id, False)
            discount_transfer_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
            discount_transfer_aml_dict.update({
                'name': 'Fee Discount (Transfer)',
                'account_id': self.env.user.company_id.transfer_account_id.id,
                'currency_id': currency_id,
                'journal_id': self.discount_journal_id.id
            })
            discount_transfer_aml = aml_obj.create(discount_transfer_aml_dict)
            self.discount_move.post()
            (to_reconcile_discount_aml | discount_transfer_aml).reconcile()

        move.post()
        self.payment_lines.register_payment(reconcile_line_rel=to_reconcile_due_amls_dict)

        return move

    @api.multi
    def post(self):
        if not self.student_id:
            return super(SsFeePayment, self).post()
        if self.amount <= 0.0:
            raise UserError('Please provide a positive non-zero Amount.')
        if not self.name or self.name == 'New':
            self.name = self.env['ir.sequence'].with_context(ir_sequence_date=self.payment_date).next_by_code(
                'account.payment.fee')

        self.payment_lines.filtered(lambda s: s.current_pay_amount <= 0.0 and s.discounted_residual > 0.0).unlink()

        if self.amount < sum(self.payment_lines.mapped('current_pay_amount')):
            raise UserError('Please check the Amount, which is not enough for this much Fees to pay.')
        if self.state != 'draft':
            raise UserError(_("Only a draft payment can be posted."))

        self.fee_ids = self.payment_lines.mapped('fee_id')
        self.invoice_ids = self.payment_lines.mapped('fee_id.invoice_id')

        move = self._create_payment_entry(self.amount * -1)

        self.write({
            'state': 'posted',
            'move_name': move.name,
        })


class FeePaymentLine(models.Model):
    _name = 'account.payment.line'

    @api.one
    @api.depends('fee_id', 'discount_mode', 'discount')
    def get_net_residual(self):
        self.discount_value = self.residual * (self.discount/100) if self.discount_mode == 'percent' else self.discount
        self.discounted_residual = self.residual - self.discount_value
        if self.fee_payment_id.fee_payment_difference > 0.0 and self.fee_payment_id.fee_payment_difference_handling == 'advance':
            self.current_pay_amount = self.discounted_residual
        else:
            if self.state == 'open':
                self.current_pay_amount = self.discounted_residual

    fee_payment_id = fields.Many2one('account.payment', required=True, ondelete='cascade')
    fee_payment_id_m2m = fields.Many2many('account.payment')

    fee_id = fields.Many2one('ss.fee', required=True, ondelete='restrict', delegate=True)

    discount_method = fields.Selection([('manual', 'M'), ('auto', 'A')],
                                       default='manual')

    discount_mode = fields.Selection([('value', '#'), ('percent', '%')], default='value')
    discount = fields.Float('Discount')

    discount_value = fields.Float('Discount in Value', compute='get_net_residual', store=True)
    discounted_residual = fields.Monetary('Net Pay', compute='get_net_residual', store=True)
    current_pay_amount = fields.Monetary('Amount Pay')

    @api.onchange('fee_payment_id', 'current_pay_amount')
    def reset_parent_amount(self):
        return {'value': {'fee_payment_id_m2m': [(4, self.fee_payment_id.id), (1, self.fee_payment_id.id, {'amount': 10})]}}

    @api.multi
    def register_payment(self, reconcile_line_rel={}):
        for line in self:
            if line.state == 'open' and reconcile_line_rel.get(line.id):
                fee_aml = line.fee_id.move_id.line_ids.filtered(
                    lambda s: not s.reconciled and s.account_id.internal_type == 'receivable')
                self.env['account.partial.reconcile'].create({
                    'debit_move_id': fee_aml.id,
                    'credit_move_id': reconcile_line_rel[line.id],
                    'amount': line.current_pay_amount + line.discount_value,
                    'amount_currency': 0.0,
                    'currency_id': line.currency_id.id if
                    line.currency_id.id != self.env.user.company_id.currency_id.id else False,
                })
            if line.state == 'validated' and line.fee_id.reconciled:
                line.fee_id.write({'state': 'advanced'})
