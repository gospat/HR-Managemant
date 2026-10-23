from datetime import date
from django.apps import apps
from django.db.models import FileField
from django.contrib.auth.models import Permission
from django.test import TestCase
from unittest.mock import patch
from types import SimpleNamespace
from horilla.testkit import make_company, make_employee, make_user
from horilla.testkit.factories import (
    make_contract,
    make_leave_type,
    make_leave_request,
    make_recruitment,
    make_candidate,
)
from university.documents.rules import RULES, NEVER_SERVE
from university.documents.access import can_read_media


class UploadRuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company("Attachment University")
        cls.other = make_company("Other institution")
        cls.owner = make_employee(company=cls.company, email="owner@rule.test")
        cls.peer = make_employee(company=cls.company, email="peer@rule.test")
        cls.outsider = make_employee(company=cls.other, email="other@rule.test")
        cls.root = make_user("rule-root", is_superuser=True)

    def test_every_upload_model_and_relationship_is_classified(self):
        actual = {
            m._meta.label
            for m in apps.get_models()
            if not m._meta.model_name.startswith("historical")
            and any(isinstance(f, FileField) for f in m._meta.fields)
        }
        self.assertEqual(actual, set(RULES) | set(NEVER_SERVE) | {"base.Company"})
        for label, (fields, owners, companies) in RULES.items():
            model = apps.get_model(label)
            for field in fields:
                self.assertIsInstance(model._meta.get_field(field), FileField)
            for owner in owners:
                model.objects.filter(
                    **{
                        (owner + "__" if owner else "")
                        + "employee_work_info__company_id_id": 1
                    }
                ).query
            for company in companies:
                model.objects.filter(**{company: 1}).query

    def test_contract_and_reimbursement_files_are_owner_and_institution_scoped(self):
        contract = make_contract(employee=self.owner, start_date=date(2020, 1, 1))
        contract.contract_document = "payroll/contract/contract_document/private.pdf"
        contract.save(update_fields=["contract_document"])
        self.assertTrue(
            can_read_media(self.owner.employee_user_id, contract.contract_document.name)
        )
        self.assertFalse(
            can_read_media(self.peer.employee_user_id, contract.contract_document.name)
        )
        user = self.outsider.employee_user_id
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="payroll", codename="view_contract"
            )
        )
        self.assertFalse(can_read_media(user, contract.contract_document.name))
        model = apps.get_model("payroll.Reimbursement")
        with patch(
            "payroll.models.models.horilla_middlewares._thread_locals",
            SimpleNamespace(
                request=SimpleNamespace(user=self.root, session={}, POST={})
            ),
        ):
            row = model.objects.create(
                title="Synthetic expense",
                employee_id=self.owner,
                allowance_on=date(2026, 1, 1),
                attachment="payroll/reimbursement/attachment/expense.pdf",
            )
        self.assertTrue(
            can_read_media(self.owner.employee_user_id, row.attachment.name)
        )
        self.assertFalse(
            can_read_media(self.peer.employee_user_id, row.attachment.name)
        )

    def test_leave_attachments_and_recruitment_files_need_proper_authority(self):
        leave = make_leave_request(
            employee=self.owner,
            leave_type=make_leave_type(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1),
        )
        leave.attachment = "leave/leaverequest/attachment/evidence.pdf"
        leave.save(update_fields=["attachment"])
        self.assertTrue(
            can_read_media(self.owner.employee_user_id, leave.attachment.name)
        )
        self.assertFalse(
            can_read_media(self.peer.employee_user_id, leave.attachment.name)
        )
        candidate = make_candidate(
            recruitment=make_recruitment(company=self.company),
            email="candidate@rule.test",
        )
        candidate.resume = "recruitment/candidate/resume/cv.pdf"
        candidate.save(update_fields=["resume"])
        self.assertFalse(
            can_read_media(self.owner.employee_user_id, candidate.resume.name)
        )
        user = self.peer.employee_user_id
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="recruitment", codename="view_candidate"
            )
        )
        user = type(user).objects.get(pk=user.pk)
        self.assertTrue(can_read_media(user, candidate.resume.name))

    def test_cross_institution_project_membership_cannot_expand_file_scope(self):
        project = apps.get_model("project.Project").objects.create(
            title="Private project",
            company_id=self.other,
            start_date=date(2026, 1, 1),
            description="Synthetic",
        )
        task = apps.get_model("project.Task").objects.create(
            title="Private task",
            project=project,
            description="Synthetic",
            document="project/task/document/private.pdf",
        )
        task.task_members.add(self.owner)
        self.assertFalse(
            can_read_media(self.owner.employee_user_id, task.document.name)
        )

    def test_backup_credentials_are_never_downloadable_even_by_administrators(self):
        row = apps.get_model("horilla_backup.GoogleDriveBackup").objects.create(
            gdrive_folder_id="synthetic",
            oauth_credentials_file="horilla_backup/googledrivebackup/oauth_credentials_file/test.json",
        )
        self.assertFalse(can_read_media(self.root, row.oauth_credentials_file.name))
