"""
Fix FK constraints for all events_* tables so CASCADE / SET NULL work at
the PostgreSQL level, not only through the Django ORM.
"""
from django.db import migrations

# ── helper ────────────────────────────────────────────────────────────────────

def _fix(cursor, table, column, ref_table, ref_col, on_delete):
    """
    Drop the existing FK on (table.column → ref_table.ref_col) and recreate
    it with the requested ON DELETE rule.
    """
    cursor.execute("""
        DO $$
        DECLARE v_con text;
        BEGIN
            SELECT tc.constraint_name INTO v_con
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
            JOIN information_schema.key_column_usage ccu
                ON rc.unique_constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name   = %(table)s
              AND kcu.column_name = %(col)s
              AND ccu.table_name  = %(ref)s;

            IF v_con IS NOT NULL THEN
                EXECUTE format('ALTER TABLE %(tbl_id)s DROP CONSTRAINT %%I', v_con);
            END IF;

            EXECUTE format(
                'ALTER TABLE %(tbl_id)s '
                'ADD CONSTRAINT %(new_con)s '
                'FOREIGN KEY (%(col_id)s) '
                'REFERENCES %(ref_id)s(%(ref_col_id)s) '
                '%(on_delete)s '
                'DEFERRABLE INITIALLY DEFERRED'
            );
        END $$;
    """ % {
        'tbl_id':    table,
        'col_id':    column,
        'ref_id':    ref_table,
        'ref_col_id': ref_col,
        'new_con':   f'{table}_{column}_fk',
        'on_delete': on_delete,
    }, {'table': table, 'col': column, 'ref': ref_table})


# ── forward ───────────────────────────────────────────────────────────────────

def fix_events_fks(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as c:

        # ── FK → auth_user ──────────────────────────────────────────────────
        # events_event.owner_id  → CASCADE
        c.execute("""
            DO $$
            DECLARE v_con text;
            BEGIN
                SELECT tc.constraint_name INTO v_con
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.referential_constraints rc
                    ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.key_column_usage ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'events_event'
                  AND kcu.column_name = 'owner_id'
                  AND ccu.table_name = 'auth_user';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE events_event DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE events_event
                    ADD CONSTRAINT events_event_owner_id_fk
                    FOREIGN KEY (owner_id) REFERENCES auth_user(id)
                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # events_eventtemplate.created_by_id  → SET NULL
        c.execute("""
            DO $$
            DECLARE v_con text;
            BEGIN
                SELECT tc.constraint_name INTO v_con
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.referential_constraints rc
                    ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.key_column_usage ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'events_eventtemplate'
                  AND kcu.column_name = 'created_by_id'
                  AND ccu.table_name = 'auth_user';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE events_eventtemplate DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE events_eventtemplate
                    ADD CONSTRAINT events_eventtemplate_created_by_id_fk
                    FOREIGN KEY (created_by_id) REFERENCES auth_user(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # events_enginemetrics.user_id  → CASCADE
        c.execute("""
            DO $$
            DECLARE v_con text;
            BEGIN
                SELECT tc.constraint_name INTO v_con
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.referential_constraints rc
                    ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.key_column_usage ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'events_enginemetrics'
                  AND kcu.column_name = 'user_id'
                  AND ccu.table_name = 'auth_user';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE events_enginemetrics DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE events_enginemetrics
                    ADD CONSTRAINT events_enginemetrics_user_id_fk
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # ── FK → events_event ───────────────────────────────────────────────
        for table, column in [
            ('events_enginemetrics', 'event_id'),
            ('events_eventalert',    'event_id'),
            ('events_eventmodule',   'event_id'),
            ('events_momento',       'evento_id'),
        ]:
            c.execute(f"""
                DO $$
                DECLARE v_con text;
                BEGIN
                    SELECT tc.constraint_name INTO v_con
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.referential_constraints rc
                        ON tc.constraint_name = rc.constraint_name
                    JOIN information_schema.key_column_usage ccu
                        ON rc.unique_constraint_name = ccu.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name   = '{table}'
                      AND kcu.column_name = '{column}'
                      AND ccu.table_name  = 'events_event';
                    IF v_con IS NOT NULL THEN
                        EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', v_con);
                    END IF;
                    ALTER TABLE {table}
                        ADD CONSTRAINT {table}_{column}_fk
                        FOREIGN KEY ({column}) REFERENCES events_event(id)
                        ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
                END $$;
            """)

        # events_event.template_id  → SET NULL
        c.execute("""
            DO $$
            DECLARE v_con text;
            BEGIN
                SELECT tc.constraint_name INTO v_con
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.referential_constraints rc
                    ON tc.constraint_name = rc.constraint_name
                JOIN information_schema.key_column_usage ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = 'events_event'
                  AND kcu.column_name = 'template_id'
                  AND ccu.table_name = 'events_eventtemplate';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE events_event DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE events_event
                    ADD CONSTRAINT events_event_template_id_fk
                    FOREIGN KEY (template_id) REFERENCES events_eventtemplate(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # events_eventtemplate sub-tables → CASCADE
        for table, column in [
            ('events_templatemodule',       'template_id'),
            ('events_templatetask',         'template_id'),
            ('events_templatebudgetitem',   'template_id'),
            ('events_templatechecklistitem','template_id'),
        ]:
            c.execute(f"""
                DO $$
                DECLARE v_con text;
                BEGIN
                    SELECT tc.constraint_name INTO v_con
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.referential_constraints rc
                        ON tc.constraint_name = rc.constraint_name
                    JOIN information_schema.key_column_usage ccu
                        ON rc.unique_constraint_name = ccu.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name   = '{table}'
                      AND kcu.column_name = '{column}'
                      AND ccu.table_name  = 'events_eventtemplate';
                    IF v_con IS NOT NULL THEN
                        EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I', v_con);
                    END IF;
                    ALTER TABLE {table}
                        ADD CONSTRAINT {table}_{column}_fk
                        FOREIGN KEY ({column}) REFERENCES events_eventtemplate(id)
                        ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
                END $$;
            """)


def reverse_events_fks(apps, schema_editor):
    """Reverse: drop the new named constraints (Django will recreate originals on migrate)."""
    if schema_editor.connection.vendor != 'postgresql':
        return
    constraints = [
        ('events_event',                'events_event_owner_id_fk'),
        ('events_event',                'events_event_template_id_fk'),
        ('events_eventtemplate',        'events_eventtemplate_created_by_id_fk'),
        ('events_enginemetrics',        'events_enginemetrics_user_id_fk'),
        ('events_enginemetrics',        'events_enginemetrics_event_id_fk'),
        ('events_eventalert',           'events_eventalert_event_id_fk'),
        ('events_eventmodule',          'events_eventmodule_event_id_fk'),
        ('events_momento',              'events_momento_evento_id_fk'),
        ('events_templatemodule',       'events_templatemodule_template_id_fk'),
        ('events_templatetask',         'events_templatetask_template_id_fk'),
        ('events_templatebudgetitem',   'events_templatebudgetitem_template_id_fk'),
        ('events_templatechecklistitem','events_templatechecklistitem_template_id_fk'),
    ]
    with schema_editor.connection.cursor() as c:
        for table, con in constraints:
            c.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE constraint_name = '{con}'
                    ) THEN
                        ALTER TABLE {table} DROP CONSTRAINT {con};
                    END IF;
                END $$;
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_event_layout_config'),
    ]

    operations = [
        migrations.RunPython(fix_events_fks, reverse_events_fks),
    ]
