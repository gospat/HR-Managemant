"""Populate one institution with a realistic staff body so the directory can be exercised.

Names are drawn from a fixed pool, so the same roster is produced on every run and
a staff member is identified by email. Re-running adds only what is missing and
never rewrites an existing record. Seeded accounts are directory entries, not
logins: they receive no usable password, so activation stays a separate action.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from base.models import Company, Department
from employee.models import Employee
from hr_auth.models import HorillaUser
from university.people.models import Faculty
from university.people.services import create_staff

EMAIL_DOMAIN = "bellsuniversity.edu.ng"

# Faculties and the directorates that sit alongside them; codes satisfy the
# per-institution unique code constraint.
FACULTIES = {
    "College of Engineering": "ENG",
    "College of Science and Technology": "CST",
    "College of Management Sciences": "CMS",
    "College of Environmental Sciences": "CES",
    "Registry": "REG",
    "Bursary": "BUR",
    "University Library": "LIB",
    "ICT and Systems": "ICT",
    "Physical Planning and Works": "PPW",
    "Health Services": "MED",
}

# College -> department -> one staff member per listed rank.
TEACHING_DEPARTMENTS = {
    "College of Engineering": {
        "Mechanical Engineering": ["Professor", "Senior Lecturer", "Lecturer I"],
        "Electrical and Electronics Engineering": [
            "Associate Professor",
            "Lecturer I",
            "Assistant Lecturer",
        ],
        "Civil Engineering": ["Senior Lecturer", "Lecturer II", "Graduate Assistant"],
    },
    "College of Science and Technology": {
        "Computer Science": ["Professor", "Senior Lecturer", "Lecturer I"],
        "Physics": ["Associate Professor", "Lecturer II", "Graduate Assistant"],
        "Chemistry": ["Senior Lecturer", "Lecturer I", "Assistant Lecturer"],
        "Mathematics": ["Professor", "Lecturer I", "Lecturer II"],
    },
    "College of Management Sciences": {
        "Accounting": ["Professor", "Senior Lecturer", "Lecturer I"],
        "Business Administration": [
            "Associate Professor",
            "Lecturer II",
            "Assistant Lecturer",
        ],
        "Economics": ["Senior Lecturer", "Lecturer I", "Graduate Assistant"],
    },
    "College of Environmental Sciences": {
        "Architecture": ["Professor", "Senior Lecturer", "Lecturer I"],
        "Building Technology": ["Lecturer I", "Lecturer II", "Assistant Lecturer"],
    },
}

# Directorate -> department -> one staff member per listed grade. The directorate
# is a faculty record; the department is where the staff member is actually posted.
NON_TEACHING_DEPARTMENTS = {
    "Registry": {
        "Registry": [
            "Registrar",
            "Deputy Registrar",
            "Assistant Registrar",
            "Administrative Officer",
        ],
    },
    "Bursary": {
        "Bursary": ["Bursar", "Chief Accountant", "Senior Accountant", "Accountant I"],
    },
    "University Library": {
        "University Library": [
            "University Librarian",
            "Senior Librarian",
            "Librarian I",
            "Library Officer",
        ],
    },
    "ICT and Systems": {
        "ICTRC": [
            "Director, ICT",
            "Senior Systems Analyst",
            "Systems Analyst",
            "Technologist I",
        ],
    },
    "Physical Planning and Works": {
        "Physical Planning and Works": [
            "Director, Works",
            "Senior Engineer",
            "Engineer II",
            "Technician",
        ],
    },
    "Health Services": {
        "Health Services": [
            "Chief Medical Officer",
            "Senior Nurse",
            "Nurse I",
            "Health Assistant",
        ],
    },
}

FIRST_NAMES = (
    "Adebayo", "Adekunle", "Adedayo", "Adeola", "Adenike", "Adetokunbo",
    "Adewale", "Ayodeji", "Bolanle", "Babatunde", "Bukola", "Chiamaka",
    "Chidinma", "Chinedu", "Chukwuemeka", "Damilola", "Ebunoluwa", "Emeka",
    "Eniola", "Ezinne", "Fadeke", "Folasade", "Funmilayo", "Gbemisola",
    "Ifeanyi", "Ifeoma", "Ijeoma", "Iyabo", "Kehinde", "Kemi", "Morounmubo",
    "Ndidi", "Ngozi", "Nkechi", "Nnamdi", "Obinna", "Okechukwu", "Olabisi",
    "Oladipo", "Olajumoke", "Olanrewaju", "Olusegun", "Olamide", "Omobolanle",
    "Onyeka", "Opeyemi", "Osinachi", "Oyindamola", "Rukayat", "Segun",
    "Shakirat", "Taiwo", "Temitope", "Titi", "Tolulope", "Uche", "Ugochukwu",
    "Yakubu", "Yewande", "Zainab",
)

LAST_NAMES = (
    "Adeyemi", "Adebisi", "Adesina", "Afolabi", "Agboola", "Ajayi", "Akinola",
    "Akinyemi", "Alabi", "Anyaegbu", "Aremu", "Awolowo", "Balogun", "Bassey",
    "Chukwu", "Dada", "Danjuma", "Eke", "Eze", "Fabunmi", "Falana", "Gbadamosi",
    "Ibrahim", "Ilori", "Iroegbu", "Jibowu", "Kalu", "Lawal", "Mabogunje",
    "Mohammed", "Musa", "Nwachukwu", "Nwosu", "Obi", "Odili", "Ogundipe",
    "Ogunsanya", "Ojo", "Okonjo", "Okoro", "Oladipo", "Olaoye", "Olumide",
    "Omotola", "Onwuka", "Opara", "Osagie", "Osunlana", "Oyebode", "Sanusi",
    "Shittu", "Suleiman", "Tijani", "Ugwu", "Umeh", "Usman", "Williams",
    "Yusuf", "Uzodinma", "Oyelaran",
)


class Command(BaseCommand):
    help = "Create a realistic staff body for one institution; never issues passwords or overwrites records."

    def add_arguments(self, parser):
        parser.add_argument("--company", type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        company = Company.objects.filter(pk=options["company"]).first()
        if company is None:
            raise CommandError("Choose an existing institution ID.")
        actor = (
            HorillaUser.objects.filter(is_superuser=True, is_active=True)
            .order_by("pk")
            .first()
        )
        if actor is None:
            raise CommandError(
                "Create an administrator first so seeded changes can be attributed."
            )
        faculties = self._faculties(company)
        departments = self._departments(company)
        created = skipped = 0
        for person in self._plan():
            if Employee.objects.entire().filter(email=person["email"]).exists():
                skipped += 1
                continue
            create_staff(
                actor=actor,
                data={
                    "company_id": company.pk,
                    "email": person["email"],
                    "first_name": person["first_name"],
                    "last_name": person["last_name"],
                    "phone": person["phone"],
                    "staff_number": person["staff_number"],
                    "category": person["category"],
                    "rank": person["rank"],
                    "department_id": departments[person["department"]].pk,
                    "faculty_id": faculties[person["faculty"]].pk,
                },
            )
            created += 1
        self.stdout.write(
            f"Staff body ready: {created} created, {skipped} already present. "
            "No passwords were issued - seeded accounts cannot sign in until an "
            "administrator activates them."
        )

    def _faculties(self, company):
        faculties = {}
        for name, code in FACULTIES.items():
            faculty = Faculty.objects.entire().filter(company=company, code=code).first()
            if faculty is None:
                faculty = Faculty.objects.create(company=company, name=name, code=code)
            faculties[name] = faculty
        return faculties

    def _departments(self, company):
        departments = {}
        for groups in (TEACHING_DEPARTMENTS, NON_TEACHING_DEPARTMENTS):
            for names in groups.values():
                for name in names:
                    if name in departments:
                        continue
                    department = (
                        Department.objects.entire()
                        .filter(department=name, company_id=company)
                        .first()
                    )
                    if department is None:
                        department = Department.objects.create(department=name)
                        department.company_id.add(company)
                    departments[name] = department
        return departments

    def _plan(self):
        """Yield one deterministic staff record per established grade."""
        index = 0
        for category, groups in (
            ("teaching", TEACHING_DEPARTMENTS),
            ("non_teaching", NON_TEACHING_DEPARTMENTS),
        ):
            for parent, departments in groups.items():
                for department, ranks in departments.items():
                    for rank in ranks:
                        yield self._person(
                            index, category, department, parent, rank
                        )
                        index += 1

    def _person(self, index, category, department, faculty, rank):
        first = FIRST_NAMES[index]
        # Stride long enough to stay coprime with the pool, so no two staff share
        # a name even though first names alone would already be unique.
        last = LAST_NAMES[(index * 7) % len(LAST_NAMES)]
        return {
            "first_name": first,
            "last_name": last,
            "email": f"{first}.{last}@{EMAIL_DOMAIN}".lower(),
            "phone": f"0{8030000000 + index}",
            "staff_number": f"BUT/STF/{index + 1:04d}",
            "category": category,
            "department": department,
            "faculty": faculty,
            "rank": rank,
        }
