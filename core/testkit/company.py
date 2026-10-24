"""Helpers for testing HrCompanyManager tenancy filtering."""

from __future__ import annotations

from core.hr_middlewares import get_selected_company, set_selected_company


def clear_selected_company() -> None:
    set_selected_company(None)


class CompanyFilterTestMixin:
    """
    Set/clear the ContextVar used by ``HrCompanyManager.get_queryset``.

    Prefer this over mutating model class attributes — current Bells Tech
    tenancy reads ``get_selected_company()``, not ``model.company_filter``.
    """

    def set_company_context(self, company_id) -> None:
        set_selected_company(company_id)

    def clear_company_context(self) -> None:
        clear_selected_company()

    def tearDown(self) -> None:
        clear_selected_company()
        super().tearDown()

    def assert_selected_company(self, expected) -> None:
        self.assertEqual(get_selected_company(), expected)
