"""
Fix FK constraints at the PostgreSQL level so that CASCADE and SET NULL
behave correctly when manipulating data directly via SQL (not just via Django ORM).

Django creates FK constraints as NO ACTION by default and handles cascade/set-null
in Python. This migration adds the proper ON DELETE rules at the database level.
"""
from django.db import migrations


def fix_account_fks(apps, schema_editor):
    # PL/pgSQL solo aplica en PostgreSQL; SQLite maneja FKs vía ORM y PRAGMA
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as c:
        # accounts_userprofile.user_id  →  ON DELETE CASCADE
        c.execute("""
            DO $$
            DECLARE v_con text;
            BEGIN
                SELECT tc.constraint_name INTO v_con
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name   = 'accounts_userprofile'
                  AND kcu.column_name = 'user_id';

                IF v_con IS NOT NULL THEN
                    EXECUTE format(
                        'ALTER TABLE accounts_userprofile DROP CONSTRAINT %I', v_con
                    );
                END IF;

                ALTER TABLE accounts_userprofile
                    ADD CONSTRAINT accounts_userprofile_user_id_fk
                    FOREIGN KEY (user_id)
                    REFERENCES auth_user(id)
                    ON DELETE CASCADE
                    DEFERRABLE INITIALLY DEFERRED;
            END $$;
        """)


def reverse_account_fks(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as c:
        c.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name = 'accounts_userprofile_user_id_fk'
                ) THEN
                    ALTER TABLE accounts_userprofile
                        DROP CONSTRAINT accounts_userprofile_user_id_fk;
                    ALTER TABLE accounts_userprofile
                        ADD FOREIGN KEY (user_id) REFERENCES auth_user(id);
                END IF;
            END $$;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_add_onboarding_completed'),
    ]

    operations = [
        migrations.RunPython(fix_account_fks, reverse_account_fks),
    ]
