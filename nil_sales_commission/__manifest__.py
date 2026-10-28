{
    'name': 'NIL Sales Commission',
    'version': '17.0.2.1.6',
    'category': 'CRM',
    'summary': 'Invoice-based sales commission ledger',
    'description': """
NIL Sales Commission
====================
- Creates one commission record per posted customer invoice dated after 31-May-2026.
- Automatically backfills existing eligible invoices on module install/upgrade.
- Archives historical duplicate commission rows even when different invoice records have the same invoice number, company, customer, date and currency, without changing payments.
- All commissions use LCP Total Rate Card only, including Cash and CLC; never use invoice value or Selling Price.
- Pending commissions have no accounting entry.
- Marking a commission as Paid creates and posts the accounting journal entry.
- Ruba commission is disabled and hidden from ledger and analysis.
- LCP cost and profit details are displayed read-only.
- Detailed commission ledger and pivot analysis.
- Access is restricted to the dedicated NIL Commission Manager group.
    """,
    'author': 'NIL ME',
    'license': 'LGPL-3',
    'depends': [
        'crm',
        'sale_crm',
        'account',
        'invoice_training_details',
    ],
    'data': [
        'security/commission_security.xml',
        'security/ir.model.access.csv',
        'data/commission_sequence.xml',
        'data/commission_backfill.xml',
        'views/sales_commission_views.xml',
        'views/crm_lead_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
