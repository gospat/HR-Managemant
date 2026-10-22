import os
from django.core.management.base import BaseCommand, CommandError
from university.operations.acceptance import acceptance_errors


class Command(BaseCommand):
    help = "Verify university acceptance evidence for the exact release commit."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument(
            "--revision", default=os.environ.get("HR_SOURCE_REVISION", "")
        )

    def handle(self, *args, **options):
        errors = acceptance_errors(options["manifest"], options["revision"])
        if errors:
            raise CommandError(
                "University release is blocked:\n- " + "\n- ".join(errors)
            )
        self.stdout.write(
            self.style.SUCCESS("University acceptance evidence verified.")
        )
