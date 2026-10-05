from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sync_rbac(sender, **kwargs):
    from .services import sync_rbac_catalog

    sync_rbac_catalog()


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        from . import signals  # noqa: F401

        post_migrate.connect(_sync_rbac, sender=self, dispatch_uid="accounts_sync_rbac")
