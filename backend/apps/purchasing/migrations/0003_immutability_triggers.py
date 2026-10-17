"""Database-level immutability triggers for posted GoodsReceipt and GoodsReceiptItem rows."""
from django.db import migrations

FORWARD_SQL = """
CREATE OR REPLACE FUNCTION purchasing_goodsreceipt_immutable()
RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'POSTED' THEN
        RAISE EXCEPTION 'Posted GoodsReceipt rows are immutable and cannot be %.', lower(TG_OP);
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS purchasing_goodsreceipt_immutable_trg ON purchasing_goodsreceipt;
CREATE TRIGGER purchasing_goodsreceipt_immutable_trg
BEFORE UPDATE OR DELETE ON purchasing_goodsreceipt
FOR EACH ROW EXECUTE FUNCTION purchasing_goodsreceipt_immutable();

CREATE OR REPLACE FUNCTION purchasing_goodsreceiptitem_immutable()
RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM purchasing_goodsreceipt
        WHERE id = OLD.goods_receipt_id AND status = 'POSTED'
    ) THEN
        RAISE EXCEPTION 'Posted GoodsReceiptItem rows are immutable and cannot be %.', lower(TG_OP);
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS purchasing_goodsreceiptitem_immutable_trg ON purchasing_goodsreceiptitem;
CREATE TRIGGER purchasing_goodsreceiptitem_immutable_trg
BEFORE UPDATE OR DELETE ON purchasing_goodsreceiptitem
FOR EACH ROW EXECUTE FUNCTION purchasing_goodsreceiptitem_immutable();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS purchasing_goodsreceiptitem_immutable_trg ON purchasing_goodsreceiptitem;
DROP FUNCTION IF EXISTS purchasing_goodsreceiptitem_immutable();
DROP TRIGGER IF EXISTS purchasing_goodsreceipt_immutable_trg ON purchasing_goodsreceipt;
DROP FUNCTION IF EXISTS purchasing_goodsreceipt_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("purchasing", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
