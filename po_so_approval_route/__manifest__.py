# -*- coding: utf-8 -*-
{
    'name': 'PO Dynamic Approval Process',
    'version': '17.0.0.1',
    'summary': 'Dynamic approval process for purchase orders',
    'category': 'Purchases',
    'author': 'SGT',
    'support': 'support@softguidetech.com',
    'website': 'https://softguidetech.com',
    'license': 'OPL-1',
    'price': 19,
    'currency': 'EUR',
    'description': """
Purchase Order Approval Cycle
=============================
This module provides a custom, flexible approval route for purchase orders.
Sales Order approval has been removed.
    """,
    'data': [
        'security/ir.model.access.csv',
        'security/purchase_security.xml',
        'data/purchase_approval_route.xml',
        'data/remove_sale_approval.xml',
        'views/purchase_approval_route.xml',
        'views/res_config_settings_views.xml',
    ],
    'depends': ['purchase', 'account'],
    'qweb': [],
    'images': [
        'static/description/icon.gif',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
