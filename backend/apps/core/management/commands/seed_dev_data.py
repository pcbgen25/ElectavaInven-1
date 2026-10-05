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
            if role_code == "SUPER_ADMIN":
                admin = user
        if generated:
            self.stdout.write(self.style.WARNING(f"Generated dev password for new seed users: {password}"))
        else:
            self.stdout.write("Seed users use DEV_SEED_PASSWORD from backend/.env")
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


def settings_env(key):
    from config.settings.base import env

    return env(key, default="")
