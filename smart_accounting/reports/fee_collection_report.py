from odoo import api, models

class ParticularReport(models.AbstractModel):
    _name = 'report.smart_accounting.report_fee_collection'

    def _get_data(self, data):
        modes = []
        for mod in data['journal_type']:
            modes.append(mod)

        stds = []
        for std in data['standard']:
            stds.append(std)

        divs = []
        for div in data['division']:
            divs.append(div)

        res_list = []
        period_data = self.env['account.payment'].search([('payment_date', '>=', data['from_date']),
                                                          ('payment_date', '<=', data['to_date']),
                                                          ('standard_id', '=', stds),
                                                          ('division_id', '=', divs),
                                                          ('journal_id', 'in', modes)])
        for rec in period_data:
            value = {
                'name': rec.student_id.name,
                'applied_for':rec.applied_for,
                'fee_type': rec.fee_type_ids.name,
                'date': rec.payment_date,
                'ref_name': rec.name,
                'mode': rec.journal_id.name,
                'amount': rec.amount,
            }
            res_list.append(value)
        return res_list

        new_list = []
        daily_data = self.env['account.payment'].search([('payment_date', '=', data['date']),
                                                         ('standard_id', '=', stds),
                                                         ('division_id', '=', divs),
                                                         ('journal_id', 'in', modes)])
        for rec in daily_data:
            value = {
                'name': rec.student_id.name,
                'applied_for': rec.applied_for,
                'fee_type': rec.fee_type_ids.name,
                'date': rec.payment_date,
                'ref_name': rec.name,
                'mode': rec.journal_id.name,
                'amount': rec.amount,
            }
            new_list.append(value)
        return new_list



    @api.model
    def get_report_values(self, docids, data=None):
        report_obj = self.env['ir.actions.report']
        report = report_obj._get_report_from_name('smart_accounting.report_fee_collection')
        docs = self.env['collection.wizard'].browse(data['id'])
        return {
            'doc_ids': docs.ids,
            'doc_model': report.model,
            'docs': docs,
            'data': data,
            'get_report_record': self._get_data
        }
        # return report_obj.render('smart_accounting.report_fee_collection', docargs)

