from copy import deepcopy
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, Permission
from base.models import Company
from university.governance.defaults import DEFAULTS, POLICY_VERSION
from university.governance.models import UniversityPolicy


class Command(BaseCommand):
    help = "Install provisional university policy templates; never invent Registrar approval or overwrite edits."

    def add_arguments(self, parser):
        parser.add_argument("--company", type=int, required=True)

    def handle(self, *args, **options):
        if not Company.objects.filter(pk=options["company"]).exists():
            raise CommandError("Choose an existing institution ID.")
        for module, data in DEFAULTS.items():
            UniversityPolicy.objects.get_or_create(
                company_id=options["company"],
                module=module,
                version=POLICY_VERSION,
                defaults={"configuration": deepcopy(data), "provisional": True},
            )
        groups = {
            "Bells Tech HR Officer": [
                "view_universitypolicy",
                "view_promotionrequest",
                "add_promotionrequest",
                "apply_promotion",
            ],
            "Bells Tech Promotion Reviewer": [
                "view_universitypolicy",
                "view_promotionrequest",
                "review_promotion",
            ],
            "Bells Tech Registrar": [
                "view_universitypolicy",
                "view_promotionrequest",
                "approve_promotion",
                "adopt_university_policy",
            ],
        }
        for name, codes in groups.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(
                *Permission.objects.filter(
                    content_type__app_label="university_governance", codename__in=codes
                )
            )
        Group.objects.get(name="Bells Tech HR Officer").permissions.add(
            Permission.objects.get(
                content_type__app_label="employee", codename="view_employee"
            )
        )
        self.stdout.write(
            "Provisional templates installed without overwriting policies. No users or approvals were created. Adopt reviewed templates explicitly before use."
        )
