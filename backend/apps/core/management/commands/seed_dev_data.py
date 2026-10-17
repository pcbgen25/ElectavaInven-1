"""Load DEVELOPMENT seed data. Idempotent. Refuses to run with DEBUG off unless --force."""
import os
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.components import services as component_services
from apps.components.models import Category, Component, Package, SpecificationDefinition
from apps.core import seed_data as seed
from apps.manufacturers.models import Manufacturer


class Command(BaseCommand):
    help = "Load development seed data (users, categories, spec definitions, packages, manufacturers, components)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Allow running when DEBUG is off.")
        parser.add_argument("--no-users", action="store_true", help="Do not create development users.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("Refusing to load development seed data with DEBUG off. Use --force if intended.")

        admin = None if opts["no_users"] else self._users()
        if admin is None:
            admin = User.objects.filter(is_superuser=True).first()
        mfrs = self._manufacturers(admin)
        pkgs = self._packages(admin)
        cats = self._categories(admin)
        created = self._components(admin, mfrs, pkgs, cats)
        self._phase2_3_4_demo(admin)
        self.stdout.write(self.style.SUCCESS(f"Seed complete. {created} new components. All seeded parts are DEV DATA."))

    # ------------------------------------------------------------------
    def _users(self):
        password = os.environ.get("DEV_SEED_PASSWORD") or settings_env("DEV_SEED_PASSWORD")
        generated = False
        if not password:
            password = "Dev-" + secrets.token_urlsafe(12)
            generated = True
        admin = None
        for email, first, last, role_code in seed.USERS:
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(email=email, password=password, first_name=first, last_name=last)
                user.roles.set([Role.objects.get(code=role_code)])
                if role_code == "SUPER_ADMIN":
                    user.is_staff = True
                    user.is_superuser = True
                    user.save(update_fields=["is_staff", "is_superuser"])
                self.stdout.write(f"  user {email} ({role_code})")
            elif not generated:
                user.set_password(password)
                user.save(update_fields=["password"])
            if role_code == "SUPER_ADMIN":
                admin = user
        if generated:
            self.stdout.write(self.style.WARNING(f"Generated dev password for new seed users: {password}"))
        else:
            self.stdout.write("Seed users use DEV_SEED_PASSWORD from environment / backend/.env")
        return admin

    def _manufacturers(self, admin):
        out = {}
        for m in seed.MANUFACTURERS:
            obj = Manufacturer.objects.filter(name__iexact=m["name"]).first()
            if obj is None:
                obj = Manufacturer.objects.create(**m, notes="[DEV SEED DATA]", created_by=admin, updated_by=admin)
            out[m["name"]] = obj
        return out

    def _packages(self, admin):
        out = {}
        for p in seed.PACKAGES:
            obj = Package.objects.filter(name__iexact=p["name"]).first() or Package.objects.create(
                **p, created_by=admin, updated_by=admin
            )
            out[p["name"]] = obj
        return out

    def _categories(self, admin):
        out = {}
        for code, name, parent_code, specs in seed.CATEGORIES:
            cat = Category.objects.filter(code=code).first()
            if cat is None:
                cat = Category.objects.create(
                    code=code, name=name, parent=out.get(parent_code), created_by=admin, updated_by=admin
                )
            out[code] = cat
            for spec in specs:
                SpecificationDefinition.objects.get_or_create(category=cat, key=spec["key"], defaults=spec)
        return out

    def _components(self, admin, mfrs, pkgs, cats):
        created = 0
        for c in seed.COMPONENTS:
            mfr = mfrs[c["manufacturer"]]
            norm = component_services.normalize_identifier(c["mpn"])
            if Component.objects.filter(manufacturer=mfr, mpn_normalized=norm).exists():
                continue
            self._create(admin, cats[c["category"]], c, mfr=mfr, pkg=pkgs.get(c.get("package")), notes=seed.SEED_NOTE)
            created += 1
        for g in seed.GENERIC_PARTS:
            if Component.objects.filter(name=g["name"]).exists():
                continue
            self._create(admin, cats[g["category"]], g, mfr=None, pkg=pkgs.get(g.get("package")), notes="[DEV SEED DATA] Generic internal part.")
            created += 1
        return created

    def _create(self, admin, category, spec, *, mfr, pkg, notes):
        defs = {d.key: d.pk for d in component_services.effective_definitions(category)}
        specs = [{"definition": defs[k], "value": v} for k, v in spec.get("specs", {}).items()]
        aliases = [{"alias": a, "alias_type": t} for a, t in spec.get("aliases", [])]
        component = component_services.create_component(
            data=dict(
                mpn=spec.get("mpn", ""),
                name=spec["name"],
                description=spec.get("description", ""),
                category=category,
                manufacturer=mfr,
                package=pkg,
                status=Component.Status.ACTIVE,
                lifecycle_status=spec.get("lifecycle_status", Component.Lifecycle.UNKNOWN),
                notes=notes,
            ),
            specifications=specs,
            aliases=aliases,
            user=admin,
        )
        self.stdout.write(f"  component {component.internal_part_number} {component.mpn or component.name}")

    def _phase2_3_4_demo(self, admin):
        from decimal import Decimal
        from apps.bom.models import BOM, BOMItem, BOMRevision
        from apps.inventory import services as inv_services
        from apps.inventory.models import InventoryItem, Warehouse, WarehouseLocation
        from apps.projects.models import Project
        from apps.purchasing import services as pur_services
        from apps.purchasing.models import PurchaseOrder, PurchaseRequest
        from apps.suppliers import services as sup_services
        from apps.suppliers.models import Supplier, SupplierContact, SupplierPart

        # Phase 2: Sample Project & BOM
        project, _ = Project.objects.get_or_create(
            code="PRJ-EV-BMS",
            defaults={
                "name": "EV Battery Management Controller",
                "description": "[DEV SEED DATA] 48V automotive BMS controller board.",
                "customer": "Electava Mobility Labs",
                "status": Project.Status.ACTIVE,
                "created_by": admin,
            },
        )
        bom, _ = BOM.objects.get_or_create(
            project=project,
            name="Main BMS Logic & CAN PCBA",
            defaults={
                "description": "[DEV SEED DATA] Main controller board BOM.",
                "status": BOM.Status.DRAFT,
                "created_by": admin,
            },
        )
        rev, rev_created = BOMRevision.objects.get_or_create(
            bom=bom,
            revision_number="REV A",
            defaults={
                "revision_name": "Initial Prototype",
                "description": "Initial engineering prototype revision",
                "status": BOMRevision.Status.DRAFT,
                "created_by": admin,
            },
        )
        mcu = Component.objects.filter(mpn="STM32F411VET6").first()
        can_ic = Component.objects.filter(mpn="TCAN1042HGVDRQ1").first()
        cap = Component.objects.filter(name__icontains="100nF").first()
        if rev_created and mcu and can_ic and cap:
            BOMItem.objects.create(
                revision=rev,
                component=mcu,
                designators=["U1"],
                quantity=Decimal("1"),
                description=mcu.name,
            )
            BOMItem.objects.create(
                revision=rev,
                component=can_ic,
                designators=["U2", "U3"],
                quantity=Decimal("2"),
                description=can_ic.name,
            )
            BOMItem.objects.create(
                revision=rev,
                component=cap,
                designators=["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"],
                quantity=Decimal("10"),
                description=cap.name,
            )

        # Phase 3: Sample Warehouse, Locations & Initial Stock
        wh, _ = Warehouse.objects.get_or_create(
            code="WH-MAIN",
            defaults={
                "name": "Main Electronics Store",
                "description": "[DEV SEED DATA] Primary SMT & IC storage.",
                "address": "Building A, Floor 1",
                "is_active": True,
            },
        )
        loc_ic, _ = WarehouseLocation.objects.get_or_create(
            warehouse=wh,
            code="A-01-01",
            defaults={"name": "Dry Cabinet A1 (MCU/IC)", "location_type": "CABINET"},
        )
        loc_pas, _ = WarehouseLocation.objects.get_or_create(
            warehouse=wh,
            code="B-01-01",
            defaults={"name": "SMT Reel Rack B1", "location_type": "RACK"},
        )
        if mcu and not InventoryItem.objects.filter(component=mcu, warehouse=wh).exists():
            inv_services.receive_stock(
                inv_services.Movement(
                    component=mcu,
                    warehouse=wh,
                    location=loc_ic,
                    quantity=Decimal("5"),
                    reference="SEED-INIT-MCU",
                    lot_batch="LOT-ST-2026",
                    notes="[DEV SEED DATA] Initial MCU stock",
                ),
                user=admin,
            )
        if cap and not InventoryItem.objects.filter(component=cap, warehouse=wh).exists():
            inv_services.receive_stock(
                inv_services.Movement(
                    component=cap,
                    warehouse=wh,
                    location=loc_pas,
                    quantity=Decimal("500"),
                    reference="SEED-INIT-CAP",
                    lot_batch="LOT-CAP-0603",
                    notes="[DEV SEED DATA] Initial capacitor reel stock",
                ),
                user=admin,
            )

        # Phase 4: Sample Suppliers, SupplierParts, Price Breaks, PR & PO
        digikey, _ = Supplier.objects.get_or_create(
            code="SUP-0001",
            defaults={
                "name": "DigiKey Electronics",
                "legal_name": "Digi-Key Corporation",
                "website": "https://www.digikey.com",
                "email": "orders@digikey.example.com",
                "phone": "+1-800-344-4539",
                "country": "USA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "lead_time_days": 5,
                "status": Supplier.Status.ACTIVE,
                "rating": 5,
                "notes": "[DEV SEED DATA] Authorized global distributor.",
                "created_by": admin,
            },
        )
        SupplierContact.objects.get_or_create(
            supplier=digikey,
            name="Sarah Jenkins",
            defaults={
                "role": "Key Account Manager",
                "email": "s.jenkins@digikey.example.com",
                "phone": "+1-800-344-4539",
                "is_primary": True,
            },
        )
        mouser, _ = Supplier.objects.get_or_create(
            code="SUP-0002",
            defaults={
                "name": "Mouser Electronics",
                "legal_name": "Mouser Electronics, Inc.",
                "website": "https://www.mouser.com",
                "email": "sales@mouser.example.com",
                "phone": "+1-800-346-6873",
                "country": "USA",
                "currency": "USD",
                "payment_terms": "Net 30",
                "lead_time_days": 6,
                "status": Supplier.Status.ACTIVE,
                "rating": 5,
                "notes": "[DEV SEED DATA] Authorized semiconductor distributor.",
                "created_by": admin,
            },
        )

        if mcu and not SupplierPart.objects.filter(supplier=digikey, component=mcu).exists():
            sup_services.create_supplier_part(
                user=admin,
                data={
                    "supplier": digikey,
                    "component": mcu,
                    "supplier_part_number": "497-14912-ND",
                    "unit_price": Decimal("5.4500"),
                    "currency": "USD",
                    "moq": Decimal("1"),
                    "order_multiple": Decimal("1"),
                    "lead_time_days": 5,
                    "is_preferred": True,
                },
                price_breaks=[
                    {"min_quantity": Decimal("1"), "unit_price": Decimal("5.4500"), "currency": "USD"},
                    {"min_quantity": Decimal("25"), "unit_price": Decimal("4.8500"), "currency": "USD"},
                    {"min_quantity": Decimal("100"), "unit_price": Decimal("4.2500"), "currency": "USD"},
                ],
            )
        if mcu and not SupplierPart.objects.filter(supplier=mouser, component=mcu).exists():
            sup_services.create_supplier_part(
                user=admin,
                data={
                    "supplier": mouser,
                    "component": mcu,
                    "supplier_part_number": "511-STM32F411VET6",
                    "unit_price": Decimal("5.6000"),
                    "currency": "USD",
                    "moq": Decimal("1"),
                    "order_multiple": Decimal("1"),
                    "lead_time_days": 6,
                    "is_preferred": False,
                },
                price_breaks=[
                    {"min_quantity": Decimal("1"), "unit_price": Decimal("5.6000"), "currency": "USD"},
                    {"min_quantity": Decimal("25"), "unit_price": Decimal("4.9000"), "currency": "USD"},
                ],
            )
        if can_ic and not SupplierPart.objects.filter(supplier=digikey, component=can_ic).exists():
            sup_services.create_supplier_part(
                user=admin,
                data={
                    "supplier": digikey,
                    "component": can_ic,
                    "supplier_part_number": "296-46952-1-ND",
                    "unit_price": Decimal("0.9800"),
                    "currency": "USD",
                    "moq": Decimal("10"),
                    "order_multiple": Decimal("10"),
                    "lead_time_days": 4,
                    "is_preferred": True,
                },
                price_breaks=[
                    {"min_quantity": Decimal("10"), "unit_price": Decimal("0.9800"), "currency": "USD"},
                    {"min_quantity": Decimal("100"), "unit_price": Decimal("0.7900"), "currency": "USD"},
                ],
            )

        if can_ic and not PurchaseRequest.objects.exists():
            pur_services.create_purchase_request(
                user=admin,
                data={
                    "title": "Prototype CAN Transceiver & MCU Replenishment",
                    "project": project,
                    "bom_revision": rev,
                    "priority": "HIGH",
                    "notes": "[DEV SEED DATA] Sample purchase request for EV BMS build.",
                },
                items=[
                    {
                        "component": can_ic,
                        "quantity": Decimal("50"),
                        "preferred_supplier": digikey,
                        "estimated_unit_price": Decimal("0.9800"),
                        "currency": "USD",
                    }
                ],
            )

        if can_ic and mcu and not PurchaseOrder.objects.exists():
            po = pur_services.create_purchase_order(
                user=admin,
                data={
                    "supplier": digikey,
                    "project": project,
                    "default_warehouse": wh,
                    "currency": "USD",
                    "tax_amount": Decimal("8.5000"),
                    "shipping_amount": Decimal("15.0000"),
                    "notes": "[DEV SEED DATA] Sample sent PO ready for Goods Receipt (GRN) testing.",
                },
                items=[
                    {
                        "component": can_ic,
                        "quantity_ordered": Decimal("50"),
                        "unit_price": Decimal("0.9800"),
                    },
                    {
                        "component": mcu,
                        "quantity_ordered": Decimal("10"),
                        "unit_price": Decimal("5.4500"),
                    },
                ],
            )
            pur_services.approve_purchase_order(po, user=admin)
            pur_services.send_purchase_order(po, user=admin)


def settings_env(key):
    from config.settings.base import env

    return env(key, default="")
