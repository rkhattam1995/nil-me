from odoo import _, api, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_nil_sa_premium_invoice(self):
        self.ensure_one()
        self._nil_sa_check_premium_invoice()
        return self.env.ref('nil_sa_premium_invoice.action_premium_invoice').report_action(self)

    def _nil_sa_check_premium_invoice(self):
        self.check_access_rights('read')
        self.check_access_rule('read')
        for move in self:
            if (move.country_code != 'SA' or move.company_id.country_id.code != 'SA'
                    or move.state != 'posted' or move.move_type not in ('out_invoice', 'out_refund')):
                raise UserError(_('This report is only available for posted Saudi customer invoices and credit notes.'))
            if not move.l10n_sa_qr_code_str:
                raise UserError(_('The original Saudi invoice QR code is missing. Use the standard invoice and check the EDI status.'))


class PremiumInvoiceReport(models.AbstractModel):
    _name = 'report.nil_sa_premium_invoice.premium_invoice'
    _description = 'NIL Saudi Premium Invoice Print'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids).exists()
        if not docs or len(docs) != len(set(docids)):
            raise UserError(_('Invoice not found.'))
        docs._nil_sa_check_premium_invoice()
        return {'doc_ids': docs.ids, 'doc_model': 'account.move', 'docs': docs}
