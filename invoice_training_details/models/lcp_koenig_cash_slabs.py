# -*- coding: utf-8 -*-

from odoo import models


class TrainingCourse(models.Model):
    _inherit = 'training.course'

    def _koenig_cash_discount_pct(self):
        """
        Koenig Cash cumulative slab discount, returned as one effective
        percentage so existing downstream calculations remain unchanged:

        - First 2 seats: 25% discount
        - Seats 3 to 5: 30% discount
        - Seat 6 onward: 45% discount
        """
        self.ensure_one()

        seats = max(self.no_of_student or 0, 0)
        if not seats:
            return 0.0

        first_two = min(seats, 2)
        three_to_five = min(max(seats - 2, 0), 3)
        six_onward = max(seats - 5, 0)

        total_discount_units = (
            (first_two * 25.0)
            + (three_to_five * 30.0)
            + (six_onward * 45.0)
        )

        return total_discount_units / seats

    def _koenig_cash_discounted_total(self):
        self.ensure_one()
        seats = max(self.no_of_student or 0, 0)
        seat_rate = self.lcp_clcs_per_seat or 0.0
        discount_pct = self._koenig_cash_discount_pct()
        return seat_rate * seats * (1.0 - discount_pct / 100.0)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def _lcp_koenig_po_terms(self, courses):
        blocks = []
        for course in courses:
            seats = max(course.no_of_student or 0, 0)
            seat_rate = course.lcp_clcs_per_seat or 0.0
            discount_pct = course._koenig_cash_discount_pct()
            discounted_total = course._koenig_cash_discounted_total()
            nil_return = (
                discounted_total * 0.55
                if course.lcp_instructor_source == 'nil_me'
                else 0.0
            )
            koenig_invoice = (
                discounted_total * 0.45
                if course.lcp_instructor_source == 'nil_me'
                else discounted_total
            )

            rows = [
                ('USD / Seat', self._lcp_money(seat_rate), False),
                ('Seats', str(seats), False),
                ('Discount', 'Cumulative slabs: 25% first 2 / 30% seats 3-5 / 45% seat 6+', True),
                ('Discounted Total', self._lcp_money(discounted_total), True),
            ]
            if course.lcp_instructor_source == 'nil_me':
                rows.append((
                    'NIL ME Return 55%',
                    self._lcp_money(nil_return),
                    False,
                ))
            rows.append((
                'Koenig Invoice',
                self._lcp_money(koenig_invoice),
                True,
            ))

            blocks.append(self._lcp_html_table('', rows))
        return ''.join(blocks)
