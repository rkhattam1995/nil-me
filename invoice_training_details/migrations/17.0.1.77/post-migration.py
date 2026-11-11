# -*- coding: utf-8 -*-
"""Recompute previously zero PS totals when both Qty and Unit Price exist.

This is deliberately scoped. Do not rewrite historical price-only service
records where the new quantity/rate fields were never entered.
"""

import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    service_model = env['pro.service'].sudo()

    # Odoo 17: schedule the stored computed field explicitly so already
    # existing records do not remain at the old persisted 0.00.
    records = service_model.search([
        ('wor_hour_number', '!=', 0),
        ('hourly_rate', '!=', 0),
        ('price', '=', 0),
    ])
    if not records:
        return

    repaired = 0
    for offset in range(0, len(records), 500):
        batch = records[offset:offset + 500]
        env.add_to_compute(service_model._fields['price'], batch)
        batch._recompute_recordset(['price'])
        repaired += len(batch)

    _logger.info('Recomputed Qty × Unit Price on %d existing zero-total PS lines', repaired)
