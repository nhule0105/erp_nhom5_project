def _max_code_number(env, table, column, pattern, company_id=None):
    query = (
        f'SELECT MAX(substring({column} FROM %s)::bigint) '
        f'FROM {table} WHERE {column} ~ %s'
    )
    params = [pattern, pattern]
    if table == 'sale_order' and company_id:
        query += ' AND company_id = %s'
        params.append(company_id)
    env.cr.execute(query, params)
    return env.cr.fetchone()[0] or 0


def _set_sequence_next_number(env, sequence, next_number):
    if sequence.implementation != 'standard':
        sequence.number_next = next_number
        return

    sequence_name = f'ir_sequence_{sequence.id:03d}'
    env.cr.execute('SELECT to_regclass(%s)', [sequence_name])
    if not env.cr.fetchone()[0]:
        raise RuntimeError(f'Missing PostgreSQL sequence {sequence_name}.')
    env.cr.execute(
        'SELECT setval(%s, %s, false)',
        [sequence_name, next_number],
    )


def _synchronize_sequence(env, code, table, column, pattern):
    sequences = env['ir.sequence'].search([('code', '=', code)])
    for sequence in sequences:
        max_number = _max_code_number(
            env,
            table,
            column,
            pattern,
            sequence.company_id.id,
        )
        if max_number:
            increment = sequence.number_increment or 1
            _set_sequence_next_number(
                env,
                sequence,
                max_number + increment,
            )


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    _synchronize_sequence(
        env,
        'sale.order',
        'sale_order',
        'name',
        r'([0-9]+)$',
    )
    _synchronize_sequence(
        env,
        'custom.sales.customer.v2',
        'res_partner',
        'ref',
        r'^KH([0-9]+)$',
    )
