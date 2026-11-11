# NIL Sales Commission (Odoo 17)

## Architecture

This is a standalone custom module. It does **not** modify `cost.details`.

It adds:

- New model: `nil.sales.commission`
- Minimal extension of: `crm.lead`
- Accounting integration through: `account.move`

## Commission rule

For every won CRM opportunity:

- Salesperson = `crm.lead.user_id`
- Training value = `crm.lead.total_training_price`
- Commission = 5% of training value
- One commission record per lead

Pending commissions create **no accounting entry**.

When **Mark Paid** is clicked, the module creates and posts a journal entry:

- Debit: Commission Expense Account
- Credit: Payment / Credit Account

The commission then becomes Paid and stores the journal entry reference.

## Historical protection

Pending commissions are updated automatically if the won lead's salesperson or training value changes.

Once a commission is Paid, it is treated as a historical snapshot and is not automatically changed by later lead edits.

## Security

A dedicated group is created:

`NIL ME / Commission Manager`

Only this group has access to the commission model and menus.

By default the module assigns this group to Odoo's standard `Administrator` user (`base.user_admin`).
If your personal login is a different Odoo user, assign **Commission Manager** to your user and remove it from Administrator if needed.

## Menu

CRM > Commissions > Commission Ledger
CRM > Commissions > Analysis

## Important dependency on your existing customization

Your existing CRM customization must already provide:

`crm.lead.total_training_price`

The module reads that field dynamically and does not redefine it.


## Invoicing trigger
A commission is created only when a customer invoice linked to the CRM opportunity through its Sales Order is posted. Marking the opportunity Won does not create a commission. If the last posted invoice is reset to draft/cancelled, an unpaid Pending commission is cancelled.
