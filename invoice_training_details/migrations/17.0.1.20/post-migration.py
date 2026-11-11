# -*- coding: utf-8 -*-


def migrate(cr, version):
    # Existing CLC rows must immediately use Total Rate Card as Training Price.
    # Total Rate Card = Rate Card / Seat x Seats.
    cr.execute("""
        UPDATE training_course
           SET price = COALESCE(lcp_rate_card_per_seat, 0.0)
                       * GREATEST(COALESCE(no_of_student, 0), 0)
         WHERE payment_method = 'clc'
           AND price IS DISTINCT FROM (
               COALESCE(lcp_rate_card_per_seat, 0.0)
               * GREATEST(COALESCE(no_of_student, 0), 0)
           )
    """)
