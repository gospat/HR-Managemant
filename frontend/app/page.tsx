import {
  ArrowUpRight,
  GraduationCap,
  Users,
  CalendarDays,
  BriefcaseBusiness,
  Wallet,
  ChartNoAxesCombined,
  ShieldCheck,
} from "lucide-react";
export const dynamic = "force-dynamic";
const modules = [
  {
    name: "Promotions",
    description: "Review evidence, recommendations and Registrar approvals.",
    icon: GraduationCap,
    href: "/promotions",
  },
  {
    name: "Staff directory",
    description:
      "One place for your people, departments and employment records.",
    icon: Users,
    href: "/staff",
  },
  {
    name: "Recruitment",
    description: "Organize vacancies, applications and the hiring journey.",
    icon: BriefcaseBusiness,
    href: "/recruitment/recruitment-view/",
  },
  {
    name: "Leave & attendance",
    description: "Manage time away, attendance and approval requests.",
    icon: CalendarDays,
    href: "/leave/employee-leave/",
  },
  {
    name: "Payroll",
    description:
      "Review contracts and payroll tools. Nigerian rules require configuration.",
    icon: Wallet,
    href: "/payroll/view-contract/",
  },
  {
    name: "Performance",
    description: "Coordinate objectives, feedback and staff development.",
    icon: ChartNoAxesCombined,
    href: "/pms/objective-list-view/",
  },
];
export default async function Home() {
  let available = false;
  try {
    const response = await fetch(
      `${process.env.HR_BACKEND_URL || "http://127.0.0.1:8000"}/ready/`,
      {
        cache: "no-store",
        headers: process.env.HR_PUBLIC_URL
          ? {
              Host: new URL(process.env.HR_PUBLIC_URL).host,
              "X-Forwarded-Proto": "https",
            }
          : {},
        signal: AbortSignal.timeout(4000),
      },
    );
    available = response.ok;
  } catch {
    /* Show service availability without exposing internal errors. */
  }
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="/">
          <span className="crest">
            <img
              src="/icon.svg"
              alt="Bells University of Technology"
              style={{ width: 40, height: 40, objectFit: "contain" }}
            />
          </span>
          <span>
            BELLS UNIVERSITY<span className="brand-sub">PEOPLE & CULTURE</span>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <a className="nav active" href="/">
          Overview <span>01</span>
        </a>
        <a className="nav" href="/login/">
          HR workspace <ArrowUpRight size={16} />
        </a>
        <div className="aside-bottom">
          <ShieldCheck size={20} />
          <p>
            Built around your people.
            <small>Teaching & non-teaching staff</small>
          </p>
        </div>
      </aside>
      <main>
        <header>
          <span>
            Human Resources <span className="slash">/</span> Overview
          </span>
          <a className="sign-in" href="/login/">
            Staff sign in <ArrowUpRight size={15} />
          </a>
        </header>
        <section className="content">
          <div className="eyebrow">YOUR PEOPLE. YOUR INSTITUTION.</div>
          <div className="intro">
            <div>
              <h1>
                A better place
                <br />
                to manage your people.
              </h1>
              <p>
                A connected workspace for the people who keep your
                <br className="desktop" /> university moving — in the classroom
                and beyond.
              </p>
            </div>
            <div className="edition">
              <span className="edition-mark">
                <GraduationCap size={42} />
              </span>
              <span>Bells University of Technology</span>
              <small>Nigeria · Africa/Lagos</small>
            </div>
          </div>
          <div className="welcome">
            <div>
              <span className="tag">GET STARTED</span>
              <h2>Your HR workspace starts here.</h2>
              <p>
                Sign in to access staff records, requests and HR operations.
              </p>
            </div>
            <a className="primary" href="/login/">
              Open HR workspace <ArrowUpRight size={18} />
            </a>
          </div>
          <div className="section-title">
            <h2>Explore your workspace</h2>
            <span>Bells University of Technology</span>
          </div>
          <div className="cards">
            {modules.map(({ name, description, icon: Icon, href }) => (
              <a className="card" href={href} key={name}>
                <div className="card-top">
                  <span className="icon">
                    <Icon size={23} />
                  </span>
                  <ArrowUpRight size={18} />
                </div>
                <h3>{name}</h3>
                <p>{description}</p>
                <span className="card-link">
                  Open module <span>→</span>
                </span>
              </a>
            ))}
          </div>
          <div className="notice">
            <ShieldCheck size={21} />
            <p>
              <strong>University review and configuration</strong>
              <span>
                Staff management and promotion approvals are available. Review
                the provisional university policies and configure salary scales
                and statutory payroll rules before your first live release.
              </span>
            </p>
          </div>
          <footer>
            <span>Bells University Human Resources</span>
            <span className="service">
              <i className={available ? "online" : ""} />
              {available ? "HR service available" : "HR service unavailable"}
            </span>
          </footer>
        </section>
      </main>
    </div>
  );
}
