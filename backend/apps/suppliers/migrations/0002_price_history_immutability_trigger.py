"""Database-level immutability trigger for SupplierPriceHistory."""
from django.db import migrations

FORWARD_SQL = """
CREATE OR REPLACE FUNCTION suppliers_price_history_immutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'SupplierPriceHistory rows are immutable and cannot be %.', lower(TG_OP);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS suppliers_price_history_immutable_trg ON suppliers_supplierpricehistory;
CREATE TRIGGER suppliers_price_history_immutable_trg
BEFORE UPDATE OR DELETE ON suppliers_supplierpricehistory
FOR EACH ROW EXECUTE FUNCTION suppliers_price_history_immutable();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS suppliers_price_history_immutable_trg ON suppliers_supplierpricehistory;
DROP FUNCTION IF EXISTS suppliers_price_history_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("suppliers", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
