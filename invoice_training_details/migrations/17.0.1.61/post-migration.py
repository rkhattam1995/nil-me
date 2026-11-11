# -*- coding: utf-8 -*-
"""Repair only editable CLC WO/quotation snapshots previously zeroed on creation."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    courses = env['training.course'].search([
        ('source_training_course_id', '!=', False),
        ('payment_method', '=', 'clc'),
        ('price', '=', 0),
        ('move_id', '=', False),
    ])
    repaired = 0
    for course in courses:
        po = course.purchase_order_id
        so = course.sale_id
        if not (
            (po and po.state in ('draft', 'sent'))
            or (so and so.state in ('draft', 'sent'))
        ):
            continue
        source = course.source_training_course_id
        original_price = (
            course.snapshot_lcp_revenue
            or source.price
            or 0.0
        )
        if original_price <= 0:
            continue
        course.with_context(
            skip_lcp_clc_price_sync=True,
            skip_lcp_reprice=True,
            nil_skip_training_audit=True,
        ).write({'price': original_price})
        repaired += 1
    _logger.info('Repaired %s draft CLC WO/quotation snapshot training prices', repaired)
