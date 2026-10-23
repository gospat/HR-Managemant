from core.settings import TEMPLATES

TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "hr_crumbs.context_processors.breadcrumbs",
)
