from odoo import Command, _
from odoo.exceptions import UserError


def sync_commands(lines, items, source_field):
    """Update one line per source; never clear unrelated/manual lines.

    Adopt a unique older untagged product line. Ambiguous historical rows
    require review rather than silently adding or deleting financial lines.
    """
    commands = []
    used_ids = set()
    source_ids = {source.id for source, vals in items}
    for source, vals in items:
        linked = lines.filtered(lambda line: line[source_field].id == source.id)
        if len(linked) > 1:
            raise UserError(_('Multiple synchronized lines exist for this training/service. Review the existing lines first.'))
        if not linked:
            candidates = lines.filtered(lambda line: (
                line.id not in used_ids
                and line.display_type in (False, 'product')
                and not line.nil_sync_training_id
                and not getattr(line, 'nil_sync_service_id', False)
                and not getattr(line, 'is_downpayment', False)
                and line.product_id.id == vals['product_id']
            ))
            if len(candidates) > 1:
                raise UserError(_('More than one existing line matches this product. Review the existing lines before synchronizing.'))
            linked = candidates
        values = dict(vals, **{source_field: source.id})
        if linked:
            used_ids.add(linked.id)
            commands.append(Command.update(linked.id, values))
        else:
            commands.append(Command.create(values))
    stale = lines.filtered(lambda line: line[source_field] and line[source_field].id not in source_ids)
    commands.extend(Command.delete(line.id) for line in stale)
    return commands
