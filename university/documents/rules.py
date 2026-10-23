"""Reviewed employee/company relationships for every non-historical upload model.

Each entry is (file fields, employee-owner paths, explicit company paths).
Scope is checked on the same relationship as ownership; uploader alone is never authority.
"""

RULES = {
    "base.BaserequestFile": (
        ["file"],
        [
            "worktyperequestcomment__request_id__employee_id",
            "shiftrequestcomment__request_id__employee_id",
        ],
        [],
    ),
    "base.Attachment": (["file"], [], ["announcement_attachments__company_id"]),
    "employee.Employee": (["employee_profile"], [""], []),
    "employee.NoteFiles": (["files"], ["employeenote__employee_id"], []),
    "employee.PolicyMultipleFile": (["attachment"], [], ["policy__company_id"]),
    "employee.DisciplinaryAction": (["attachment"], ["employee_id"], []),
    "recruitment.Candidate": (
        ["profile", "resume"],
        [],
        ["recruitment_id__company_id"],
    ),
    "recruitment.StageFiles": (
        ["files"],
        [],
        ["stagenote__candidate_id__recruitment_id__company_id"],
    ),
    "recruitment.RecruitmentSurveyAnswer": (
        ["attachment"],
        [],
        ["recruitment_id__company_id"],
    ),
    "recruitment.Resume": (["file"], [], ["recruitment_id__company_id"]),
    "recruitment.CandidateDocument": (
        ["document"],
        [],
        ["candidate_id__recruitment_id__company_id"],
    ),
    "onboarding.OnboardingCandidate": (
        ["profile", "resume"],
        [],
        ["recruitment_id__company_id"],
    ),
    "onboarding.OnboardingPortal": (
        ["profile"],
        [],
        ["candidate_id__recruitment_id__company_id"],
    ),
    "leave.LeaveType": (["icon"], [], ["company_id"]),
    "leave.LeaveRequest": (["attachment"], ["employee_id"], []),
    "leave.LeaverequestFile": (
        ["file"],
        [
            "leaverequestcomment__request_id__employee_id",
            "leaveallocationrequestcomment__request_id__employee_id",
            "compensatoryleaverequestcomment__request_id__employee_id",
        ],
        [],
    ),
    "leave.LeaveAllocationRequest": (["attachment"], ["employee_id"], []),
    "leave.OverrideLeaveRequests": (["attachment"], ["employee_id"], []),
    "asset.AssetDocuments": (["file"], ["asset_report__asset_id__owner"], []),
    "asset.ReturnImages": (
        ["image"],
        [
            "return_images__assigned_to_employee_id",
            "assign_images__assigned_to_employee_id",
        ],
        [],
    ),
    "attendance.AttendanceRequestFile": (
        ["file"],
        ["attendancerequestcomment__request_id__employee_id"],
        [],
    ),
    "payroll.Contract": (["contract_document"], ["employee_id"], []),
    "payroll.OverrideLeaveRequest": (["attachment"], ["employee_id"], []),
    "payroll.ReimbursementMultipleAttachment": (
        ["attachment"],
        ["reimbursement__employee_id"],
        [],
    ),
    "payroll.Reimbursement": (["attachment"], ["employee_id"], []),
    "payroll.ReimbursementFile": (
        ["file"],
        ["reimbursementrequestcomment__request_id__employee_id"],
        [],
    ),
    "horilla_documents.Document": (["document"], ["employee_id"], []),
    "helpdesk.Attachment": (
        ["file"],
        [
            "ticket__employee_id",
            "ticket__assigned_to",
            "comment__ticket__employee_id",
            "comment__ticket__assigned_to",
        ],
        [],
    ),
    "offboarding.OffboardingStageMultipleFile": (
        ["attachment"],
        [
            "exitreason__offboarding_employee_id__employee_id",
            "offboardingnote__employee_id__employee_id",
        ],
        [],
    ),
    "project.Project": (["document"], ["managers"], ["company_id"]),
    "project.Task": (
        ["document"],
        ["task_managers", "task_members"],
        ["project__company_id"],
    ),
    "master_import.ImportJob": (["file", "error_file"], [], ["company_id"]),
}
# These files contain credentials and must not be delivered through /media/.
NEVER_SERVE = {"horilla_backup.GoogleDriveBackup": ["oauth_credentials_file"]}
