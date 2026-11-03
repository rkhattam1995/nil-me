# -*- coding: utf-8 -*-
"""Quotation-only terms. Do not use for New WO, POs, invoices or global defaults."""

from html import escape
import re

from odoo import api, fields, models


# Legal wording is intentionally copied without proofreading or alterations.
# CLC Online differs only in delivery mode and removal of On-site Catering.
# Its numbered clauses are renumbered sequentially without rewriting text.
# Original legal wording. Clause numbering is intentionally NOT stored as text.
CLC_ONSITE_TERMS = (
    "All NIL Middle East (NIL ME) terms and conditions apply; by accepting this quotation, you are accepting all terms with no exceptions.",
    "Training Location: Instructor-Led – Onsite.",
    "Trainees should use their own laptops for training.",
    "Catering: Not applicable.",
    "Cancellation Policy: Cancellations made at least 2 weeks prior to the start date will incur no charges. Cancellations made within 2 weeks of the start date will incur a 100% cancellation fee.",
    "Participant Changes: Changes or replacements of participant names or email addresses are permitted only if requested at least 2 weeks before the start date.",
    "Purchase Order and Payment: For CLC-based orders, there is no need for an official customer purchase order. Instead, an email accepting the quotation shall be shared with NIL Middle East with the following information included:",
    "All CLC prices are inclusive of VAT. Any other applicable taxes must be paid directly by the buyer to the relevant authorities and must not be deducted from the NIL ME fees.",
    "Schedule Changes: NIL Middle East reserves the right to modify program start dates and schedules. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.",
    "Exams & Vouchers: The price does not include exam costs. NIL ME is not an exam or testing center.",
    "Prices for training do not include students’ costs for tickets, accommodation, visa, etc.",
    "NIL Middle East selects certified instructors based on quality and availability.",
    "Training Language: All training is delivered in English.",
    "Offer Validity: This offer is valid until 15 days from the date of issuance.",
)

# CLC Online has no catering; only the delivery location wording differs.
CLC_ONLINE_TERMS = tuple(
    'Training Location: Instructor-Led – Online.'
    if clause == 'Training Location: Instructor-Led – Onsite.'
    else clause
    for clause in CLC_ONSITE_TERMS
    if clause != 'Catering: Not applicable.'
)

CLC_PAYMENT_SUBITEMS = (
    "SO#",
    "Available CLCs in the SO#",
    "Expiry date of the CLCs",
)

CLC_DISCLAIMER_BULLETS = (
    "Certified Courses kits ((Materials and Labs)) offered, and CLCs redeeming are provided in full cooperation with NIL Middle East’s strategic Partner and CLP “Enterone”.",
    "All classes are delivered by certified instructors.",
)

CASH_ONSITE_TERMS = "General Terms & Conditions:\n1. All NIL Middle East (NIL ME) terms and conditions apply.\n2. Trainees should use their own laptop for the training.\n3. Training Location: Onsite at customer office in XXXXXXXX. Customers must secure good internet access for the students and the instructor.\n4. Catering included in NIL ME offer.\n5. Cancellation Policy:\n• Cancellations made at least 2 weeks prior to the program start date will incur no charges.\n• Cancellations made within 2 weeks of the start date will incur a 100% cancellation fee.\n6. Changes or replacements of participant names or email addresses are permitted only if requested at least 2 weeks before the start date.\n7. Schedule Changes: NIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.\n8. Payment:\na. Full payment (30%) must be made in advance, due on receipt of the invoice, and 2 weeks before the training start date.\nb. Remainign (70%) should be paid against final invoice after delivery- Net30\nc. All prices are exclusive of taxes. Any applicable taxes must be paid directly by the buyer to the relevant authorities and must not be deducted from the NIL ME fees.\nd. The buyer is responsible for all bank transfer fees and charges related to payments made to the NIL Middle East XXXXXXXX (XXXXXXXX) bank account.\n9. Schedule changes\nNIL Middle East reserves the right to modify program start dates, cohort schedules, or exam dates without prior notice. While every effort will be made to maintain the original schedule, NIL ME will provide alternative options if changes occur. Such changes will not result in any legal or financial liability for NIL Middle East.\n10. Exams & Vouchers: The price does not include exam costs, NIL Middle East is not an official exam testing center and only provides exam vouchers based on separated request.\n11. Prices for training do not include students’ cost of tickets, accommodation, visa, …. Etc.\n12. NIL Middle East selects certified instructors based on quality and availability.\n13. Training Language: All training is delivered in English.\n14. Offer Validity: This offer is valid for 15 days from the date of issuance.\n\nDisclaimer:\n- Certified Courses kits ((Materials and Labs)) offered, and CLCs redeeming are provided in full cooperation with NIL Middle East’s strategic Partner and CLP “Enterone”.\n- All classes are delivered by certified instructors."


def _clc_terms_html(clauses, expected_clauses):
    """Use native editor <ol>/<li> numbering, never visible text prefixes.

    Both CLC modes share one editable numbered list with an alphabetic
    sublist inside Purchase Order and Payment, plus Disclaimer bullets.
    """
    if len(clauses) != expected_clauses:
        raise ValueError('CLC Terms clause count differs from the template')

    html = [
        '<p><strong>Terms &amp; Conditions:</strong></p>',
        '<ol style="list-style-type:decimal;padding-left:28px;">',
    ]
    payment_sections = 0

    for clause in clauses:
        html.append('<li>%s' % escape(clause))
        if clause.startswith('Purchase Order and Payment:'):
            payment_sections += 1
            html.append(
                '<ol type="a" style="list-style-type:lower-alpha;padding-left:28px;">'
            )
            for text in CLC_PAYMENT_SUBITEMS:
                html.append('<li>%s</li>' % escape(text))
            html.append('</ol>')
        html.append('</li>')

    if payment_sections != 1 or len(CLC_PAYMENT_SUBITEMS) != 3:
        raise ValueError('The CLC Payment sublist must contain a, b, c')
    if len(CLC_DISCLAIMER_BULLETS) != 2:
        raise ValueError('The CLC Disclaimer must contain two bullet items')

    html.extend([
        '</ol>',
        '<p><strong>Disclaimer:</strong></p>',
        '<ul style="list-style-type:disc;padding-left:28px;">',
    ])
    for text in CLC_DISCLAIMER_BULLETS:
        html.append('<li>%s</li>' % escape(text))
    html.append('</ul>')
    return ''.join(html)


def _clc_online_terms_html():
    return _clc_terms_html(CLC_ONLINE_TERMS, 13)


def _clc_onsite_terms_html():
    return _clc_terms_html(CLC_ONSITE_TERMS, 14)


# Native HTML lists are compatible with the existing Terms editor.
_CASH_BOLD_HEADINGS = (
    'Training Location:',
    'Catering',
    'Cancellation Policy:',
    'Schedule Changes:',
    'Payment:',
    'Schedule changes',
    'Exams & Vouchers:',
    'Training Language:',
    'Offer Validity:',
)


def _cash_heading_html(text):
    for heading in _CASH_BOLD_HEADINGS:
        if text.startswith(heading):
            return '<strong>%s</strong>%s' % (
                escape(heading), escape(text[len(heading):]),
            )
    return escape(text)


def _cash_onsite_terms_html():
    """Native decimal, bullet, and alphabetic numbering for the Terms editor."""
    lines = [line.strip() for line in CASH_ONSITE_TERMS.splitlines()]
    html = [
        '<p><strong>General Terms &amp; Conditions:</strong></p>',
        '<ol style="list-style-type:decimal;padding-left:28px;">',
    ]
    in_item = False
    nested = None
    in_disclaimer = False
    expected_number = 1

    for line in lines[1:]:
        if not line:
            continue
        if line == 'Disclaimer:':
            if nested:
                html.append('</%s>' % nested)
                nested = None
            if in_item:
                html.append('</li>')
                in_item = False
            html.append('</ol>')
            html.append('<p><strong>Disclaimer:</strong></p>')
            html.append('<ul style="list-style-type:disc;padding-left:28px;">')
            in_disclaimer = True
            continue

        if in_disclaimer:
            if line.startswith('- '):
                html.append('<li>%s</li>' % escape(line[2:]))
            continue

        numbered = re.match(r'^(\d+)\.\s+(.+)$', line)
        if numbered:
            if int(numbered.group(1)) != expected_number:
                raise ValueError('Incorrect Cash Onsite clause numbering')
            expected_number += 1
            if nested:
                html.append('</%s>' % nested)
                nested = None
            if in_item:
                html.append('</li>')
            html.append('<li%s>%s' % (
                ' style="color:#ff0000;"' if numbered.group(1) == '4' else '',
                _cash_heading_html(numbered.group(2)),
            ))
            in_item = True
            continue

        bullet = re.match(r'^•\s+(.+)$', line)
        lettered = re.match(r'^[a-d]\.\s+(.+)$', line)
        if bullet or lettered:
            kind = 'ul' if bullet else 'ol'
            if nested != kind:
                if nested:
                    html.append('</%s>' % nested)
                html.append(
                    '<ul style="list-style-type:disc;padding-left:28px;">'
                    if bullet else
                    '<ol type="a" style="list-style-type:lower-alpha;padding-left:28px;">'
                )
                nested = kind
            html.append('<li>%s</li>' % escape((bullet or lettered).group(1)))
            continue

        # The paragraph beneath clause 9 remains part of clause 9.
        html.append('<br/>%s' % escape(line))

    if nested:
        html.append('</%s>' % nested)
    if in_item:
        html.append('</li>')
    html.append('</ul>' if in_disclaimer else '</ol>')
    if expected_number != 15:
        raise ValueError('Cash Onsite terms must have exactly 14 clauses')
    return ''.join(html)


_QUOTATION_TERMS = {
    ('clc', 'On site'): ('CLC Onsite', CLC_ONSITE_TERMS),
    ('clc', 'Online'): ('CLC Online', CLC_ONLINE_TERMS),
    ('cash', 'On site'): ('Cash Onsite', CASH_ONSITE_TERMS),
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _nil_terms_for_new_quotation_only(self):
        """Build complete terms from training modes, never from lead-level mode."""
        self.ensure_one()
        modes = []
        for course in self.training_course_ids:
            mode = (course.payment_method, course.location)
            # Cash Online was not provided. Never silently use the On-site text.
            if mode not in _QUOTATION_TERMS:
                return False
            if mode not in modes:
                modes.append(mode)
        if not modes:
            return False
        sections = []
        for mode in modes:
            _label, terms = _QUOTATION_TERMS[mode]
            if mode == ('cash', 'On site'):
                sections.append(_cash_onsite_terms_html())
                continue
            if mode == ('clc', 'Online'):
                sections.append(_clc_online_terms_html())
                continue
            if mode == ('clc', 'On site'):
                sections.append(_clc_onsite_terms_html())
                continue
        return '<br/><br/>'.join(sections)

    def action_new_quotation(self):
        """Apply terms only when CRM's standard New Quotation button is used."""
        self.ensure_one()
        action = super().action_new_quotation()
        if action.get('res_model') != 'sale.order':
            return action
        html = self._nil_terms_for_new_quotation_only()
        if html:
            context = dict(action.get('context') or {})
            context.update({
                'default_nil_new_quotation_terms': True,
                'default_term_and_cond': html,
            })
            action['context'] = context
        return action


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    nil_new_quotation_terms = fields.Boolean(
        string='Quotation Terms Set From New Quotation',
        default=False,
        copy=False,
    )

    @api.onchange('payment_method')
    def _onchange_payment_method_terms(self):
        # The preexisting onchange prepends an Instructor/Customer header.
        # Suppress it only for the precise New Quotation records, leaving
        # Work Orders, purchase orders and all other documents untouched.
        for order in self:
            if not order.nil_new_quotation_terms:
                super(SaleOrder, order)._onchange_payment_method_terms()

    def _prepare_invoice(self):
        self.ensure_one()
        values = super()._prepare_invoice()
        if self.nil_new_quotation_terms:
            # The custom sale.order logic normally forwards these terms to
            # account.move. This content belongs ONLY to the quotation.
            values.pop('term_and_cond', None)
        return values
