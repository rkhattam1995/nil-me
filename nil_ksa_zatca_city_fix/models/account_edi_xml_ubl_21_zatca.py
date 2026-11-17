# -*- coding: utf-8 -*-
from odoo import models


class AccountEdiXmlUbl21Zatca(models.AbstractModel):
    _inherit = 'account.edi.xml.ubl_21.zatca'

    def _export_invoice_vals(self, invoice):
        vals = super()._export_invoice_vals(invoice)

        # Only Saudi sales invoices and credit notes use this fallback.
        # Leave all other invoice data and countries unchanged.
        if invoice.move_type not in ('out_invoice', 'out_refund'):
            return vals
        if invoice.company_id.country_id.code != 'SA':
            return vals

        party = (
            vals.get('vals', {})
            .get('accounting_supplier_party_vals', {})
            .get('party_vals', {})
        )
        if not party:
            return vals

        # Odoo's standard UBL exporter reads the commercial partner's city.
        # This can be empty even when the company address shows a valid city.
        city = (invoice.company_id.city or invoice.company_id.partner_id.city or '').strip()
        if not city:
            return vals

        addresses = [party.get('postal_address_vals')]
        for key in ('party_tax_scheme_vals', 'party_legal_entity_vals'):
            for entry in party.get(key, []):
                addresses.append(entry.get('registration_address_vals'))

        # Keep any existing address city unchanged; fill only missing cities.
        for address in addresses:
            if isinstance(address, dict) and not address.get('city_name'):
                address['city_name'] = city

        return vals
