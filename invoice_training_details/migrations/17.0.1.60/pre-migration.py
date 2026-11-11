# -*- coding: utf-8 -*-
"""
Odoo.sh production stability migration.

Some Odoo 17 databases can retain the official test_base_automation model
metadata while its test-only table is absent. Registry.check_tables_exist()
then logs an ERROR for base.automation.readonly.test, which makes the Odoo.sh
build red even though the model has no business use.

Create the exact lightweight table only when the model metadata exists and
the table is missing. If Odoo later initializes the test module, its normal
schema initialization can safely add constraints/indexes on top.
"""


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM ir_model WHERE model = %s LIMIT 1",
        ('base.automation.readonly.test',),
    )
    if not cr.fetchone():
        return

    cr.execute("""
        CREATE TABLE IF NOT EXISTS base_automation_readonly_test (
            id SERIAL PRIMARY KEY
        )
    """)

    columns = {
        'name': 'VARCHAR',
        'tag_id': 'INTEGER',
        'tag_name': 'VARCHAR',
        'date_automation_last': 'TIMESTAMP WITHOUT TIME ZONE',
        'create_uid': 'INTEGER',
        'create_date': 'TIMESTAMP WITHOUT TIME ZONE',
        'write_uid': 'INTEGER',
        'write_date': 'TIMESTAMP WITHOUT TIME ZONE',
    }
    for column, sql_type in columns.items():
        cr.execute(
            'ALTER TABLE base_automation_readonly_test '
            'ADD COLUMN IF NOT EXISTS "%s" %s' % (column, sql_type)
        )
