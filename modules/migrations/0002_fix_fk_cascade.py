"""
Fix FK constraints for all modules_* tables so CASCADE / SET NULL work at
the PostgreSQL level, not only through the Django ORM.
"""
from django.db import migrations


def fix_modules_fks(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as c:

        # ── FK → auth_user ──────────────────────────────────────────────────

        # modules_task.assigned_to_id  → SET NULL
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
                  AND tc.table_name   = 'modules_task'
                  AND kcu.column_name = 'assigned_to_id'
                  AND ccu.table_name  = 'auth_user';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE modules_task DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE modules_task
                    ADD CONSTRAINT modules_task_assigned_to_id_fk
                    FOREIGN KEY (assigned_to_id) REFERENCES auth_user(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # modules_attendee.user_id  → SET NULL
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
                  AND tc.table_name   = 'modules_attendee'
                  AND kcu.column_name = 'user_id'
                  AND ccu.table_name  = 'auth_user';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE modules_attendee DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE modules_attendee
                    ADD CONSTRAINT modules_attendee_user_id_fk
                    FOREIGN KEY (user_id) REFERENCES auth_user(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # modules_file.uploaded_by_id  → SET NULL
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
                  AND tc.table_name   = 'modules_file'
                  AND kcu.column_name = 'uploaded_by_id'
                  AND ccu.table_name  = 'auth_user';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE modules_file DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE modules_file
                    ADD CONSTRAINT modules_file_uploaded_by_id_fk
                    FOREIGN KEY (uploaded_by_id) REFERENCES auth_user(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # ── FK → events_event  (all CASCADE) ────────────────────────────────
        for table, column in [
            ('modules_task',      'event_id'),
            ('modules_attendee',  'event_id'),
            ('modules_file',      'event_id'),
            ('modules_budget',    'event_id'),
            ('modules_checklist', 'event_id'),
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

        # ── FK → modules_budget  (CASCADE) ──────────────────────────────────
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
                  AND tc.table_name   = 'modules_budgetitem'
                  AND kcu.column_name = 'budget_id'
                  AND ccu.table_name  = 'modules_budget';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE modules_budgetitem DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE modules_budgetitem
                    ADD CONSTRAINT modules_budgetitem_budget_id_fk
                    FOREIGN KEY (budget_id) REFERENCES modules_budget(id)
                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # ── FK → modules_task  (SET NULL) ────────────────────────────────────
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
                  AND tc.table_name   = 'modules_budgetitem'
                  AND kcu.column_name = 'related_task_id'
                  AND ccu.table_name  = 'modules_task';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE modules_budgetitem DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE modules_budgetitem
                    ADD CONSTRAINT modules_budgetitem_related_task_id_fk
                    FOREIGN KEY (related_task_id) REFERENCES modules_task(id)
                    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)

        # ── FK → modules_checklist  (CASCADE) ───────────────────────────────
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
                  AND tc.table_name   = 'modules_checklistitem'
                  AND kcu.column_name = 'checklist_id'
                  AND ccu.table_name  = 'modules_checklist';
                IF v_con IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE modules_checklistitem DROP CONSTRAINT %I', v_con);
                END IF;
                ALTER TABLE modules_checklistitem
                    ADD CONSTRAINT modules_checklistitem_checklist_id_fk
                    FOREIGN KEY (checklist_id) REFERENCES modules_checklist(id)
                    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)


def reverse_modules_fks(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    constraints = [
        ('modules_task',           'modules_task_assigned_to_id_fk'),
        ('modules_task',           'modules_task_event_id_fk'),
        ('modules_attendee',       'modules_attendee_user_id_fk'),
        ('modules_attendee',       'modules_attendee_event_id_fk'),
        ('modules_file',           'modules_file_uploaded_by_id_fk'),
        ('modules_file',           'modules_file_event_id_fk'),
        ('modules_budget',         'modules_budget_event_id_fk'),
        ('modules_budgetitem',     'modules_budgetitem_budget_id_fk'),
        ('modules_budgetitem',     'modules_budgetitem_related_task_id_fk'),
        ('modules_checklist',      'modules_checklist_event_id_fk'),
        ('modules_checklistitem',  'modules_checklistitem_checklist_id_fk'),
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
        ('modules', '0001_initial'),
        ('events',  '0005_fix_fk_cascade'),   # events must run first
    ]

    operations = [
        migrations.RunPython(fix_modules_fks, reverse_modules_fks),
    ]
