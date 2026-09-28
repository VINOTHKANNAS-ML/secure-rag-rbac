"""
Generates a synthetic "enterprise document" corpus for the Secure RAG demo.

Run:
    python generate_dataset.py

Produces:
    data/documents/*.txt   - the raw documents
    data/metadata.json     - {doc_id: {title, department, confidentiality_level, ...}}

This version mixes hand-authored policy/incident documents with templated
recurring reports (quarterly budgets, sales pipeline, incident postmortems,
board updates, sprint notes) so the vector index has enough density and
topical overlap for retrieval quality to actually matter. Everything is
generated locally from templates - no external data, no network calls.
"""

import json
import os
import random

random.seed(42)

OUT_DIR = os.path.join("data", "documents")
os.makedirs(OUT_DIR, exist_ok=True)

HAND_AUTHORED = [
    ("General", 0, "Employee Handbook Overview",
     "This handbook introduces company values, the code of conduct, office "
     "locations, and general onboarding steps for all new hires. It covers "
     "working hours, the dress code, holiday calendar, and how to request IT "
     "equipment through the internal service desk."),
    ("General", 0, "Company Mission and Values",
     "Our mission is to build reliable software that helps enterprises manage "
     "knowledge securely. Our values are transparency, ownership, customer "
     "obsession, and continuous learning. These values guide hiring, "
     "promotion, and day-to-day decision making across every department."),
    ("General", 0, "Office Facilities Guide",
     "The Hyderabad and Austin offices are open Monday through Friday, 8am to "
     "8pm. Meeting rooms can be booked via the facilities portal. Visitors "
     "must be registered at least 24 hours in advance and are required to "
     "wear a visitor badge at all times while on premises."),
    ("General", 0, "New Hire Orientation Schedule",
     "Week one covers HR paperwork, IT provisioning, and a facilities tour. "
     "Week two introduces team-specific onboarding with an assigned buddy. "
     "All new hires complete security awareness training within the first "
     "five business days."),
    ("General", 1, "Internal Wiki Usage Guidelines",
     "The internal wiki hosts engineering runbooks, HR policies, and finance "
     "templates. Employees should tag pages with the correct department and "
     "confidentiality level. Content marked Internal is visible to all "
     "employees but must never be shared with external parties."),
    ("General", 1, "IT Equipment and Software Request Policy",
     "Standard laptop refresh cycle is 3 years. Software requiring a paid "
     "license must be requested through the IT portal with manager approval. "
     "Personal devices may access email via the mobile management app only "
     "after enrolling in the company's MDM profile."),
    ("General", 1, "Company Travel Booking Guidelines",
     "All business travel must be booked through the approved travel portal "
     "to remain within policy and enable duty-of-care tracking. Economy class "
     "is standard for flights under 6 hours; business class requires VP "
     "approval for longer international travel."),

    ("HR", 1, "Leave and Time-Off Policy",
     "Full-time employees accrue 20 days of paid time off annually plus 10 "
     "public holidays. Sick leave is capped at 12 days per year. Unused PTO "
     "up to 5 days may be carried over to the following year with manager "
     "approval submitted through the HR portal."),
    ("HR", 1, "Remote Work Policy",
     "Employees may work remotely up to 3 days per week with manager sign "
     "off. Fully remote arrangements require VP approval and a documented "
     "home-office security checklist, including full-disk encryption and a "
     "company-managed VPN client."),
    ("HR", 1, "Parental Leave Policy",
     "Primary caregivers are eligible for 16 weeks of paid parental leave; "
     "secondary caregivers receive 6 weeks. Leave may be taken continuously "
     "or split within the first 12 months following birth or adoption, "
     "subject to manager and HR coordination."),
    ("HR", 1, "Employee Wellness Program Guide",
     "The wellness program includes a monthly stipend for gym memberships, "
     "quarterly mental health workshops, and an employee assistance program "
     "offering confidential counseling sessions at no cost to employees."),
    ("HR", 1, "Diversity, Equity, and Inclusion Framework",
     "The DEI framework sets annual representation goals for hiring and "
     "leadership promotion, funds employee resource groups, and requires "
     "unconscious-bias training for all hiring managers before they can "
     "approve an offer."),
    ("HR", 2, "Performance Review Cycle - Manager Guide",
     "Managers must complete calibration sessions before finalizing ratings. "
     "Ratings distribution should approximate a normal curve; ratings of "
     "'Exceeds' should not exceed 20% of any team. Compensation adjustments "
     "tied to ratings are discussed only with HR Business Partners present."),
    ("HR", 2, "Workplace Investigation Procedures",
     "All harassment or misconduct complaints are routed to the HR "
     "Investigations team within 48 hours. Investigators must maintain "
     "confidentiality, interview all named parties, and document findings in "
     "the restricted case management system before any disciplinary action."),
    ("HR", 2, "Reorganization Planning Guidelines - Managers",
     "Managers proposing a team reorganization must submit a headcount "
     "impact assessment to HR Business Partners at least 4 weeks before "
     "implementation. Any role eliminations require a documented business "
     "justification reviewed jointly by HR and Legal."),
    ("HR", 3, "Executive Compensation Bands 2026",
     "VP-level base salary bands range from 210,000 to 280,000 USD with "
     "equity grants vesting over four years. C-suite total compensation, "
     "including performance bonuses and retention grants, is reviewed "
     "annually by the Compensation Committee and is strictly need-to-know."),
    ("HR", 3, "Employee Disciplinary Case Log Q2",
     "This restricted log tracks active disciplinary cases including formal "
     "warnings, performance improvement plans, and terminations for cause. "
     "Access is limited to HR leadership and Legal; sharing case details "
     "outside this group violates company confidentiality policy."),
    ("HR", 3, "Planned Layoff - Confidential Restructuring Memo",
     "This restricted memo outlines a planned workforce reduction affecting "
     "approximately 4% of headcount concentrated in the legacy support "
     "organization, pending final board approval. Details must not be shared "
     "outside the named planning group before the announcement date."),

    ("Finance", 1, "Expense Reimbursement Policy",
     "Employees must submit expense reports within 30 days of purchase using "
     "the finance portal. Receipts are required for any expense over 25 "
     "USD. Travel expenses should follow the approved per-diem rates listed "
     "in the travel policy appendix."),
    ("Finance", 1, "Purchase Order and Procurement Guidelines",
     "Purchases under 5,000 USD may be approved by a team lead. Purchases "
     "between 5,000 and 50,000 USD require department head sign-off and a "
     "competitive quote comparison. Anything above 50,000 USD routes through "
     "the procurement committee."),
    ("Finance", 2, "Vendor Contract Renewal - Cloud Infrastructure",
     "The company renewed its primary cloud provider contract for 3 years at "
     "a 12% negotiated discount contingent on committed annual spend of 2.1 "
     "million USD. Early termination carries a penalty equal to 40% of "
     "remaining committed spend."),
    ("Finance", 2, "Annual Insurance and Risk Coverage Summary",
     "The company maintains general liability, cyber liability, and "
     "directors & officers insurance renewed annually each September. Cyber "
     "liability coverage was increased this year following the growth in "
     "customer data volume handled by the platform."),
    ("Finance", 3, "FY2026 Revenue Forecast and Investor Deck Notes",
     "Projected FY2026 revenue is 82 million USD, up 34% year over year, "
     "driven by enterprise contract expansions. This forecast is shared with "
     "the board and select investors only ahead of the public earnings "
     "release and must not be disclosed externally before that date."),
    ("Finance", 3, "M&A Due Diligence - Project Northstar",
     "Project Northstar refers to the potential acquisition of a data "
     "security startup for an estimated 45 to 60 million USD. Due diligence "
     "materials, including target financials and cap table, are restricted "
     "to the deal team and executive sponsors under NDA."),

    ("Engineering", 1, "Coding Standards and Style Guide",
     "All backend services use type-annotated Python or Go. Pull requests "
     "require at least one approving review and passing CI before merge. "
     "Commit messages should follow the conventional-commits format for "
     "automated changelog generation."),
    ("Engineering", 1, "Onboarding: Local Development Environment Setup",
     "New engineers should install the company CLI, run 'make bootstrap', "
     "and configure pre-commit hooks. Access to staging clusters is granted "
     "automatically after completing the security training module in the "
     "first week."),
    ("Engineering", 1, "On-Call Rotation Handbook",
     "Each service team maintains a weekly on-call rotation via the "
     "scheduling tool. Primary on-call must acknowledge pages within 10 "
     "minutes; unacknowledged pages escalate automatically to the secondary "
     "on-call engineer and then the engineering manager."),
    ("Engineering", 2, "System Architecture - Document Retrieval Service",
     "The retrieval service uses a vector database with metadata filters "
     "for department and confidentiality level, sitting behind an internal "
     "gateway that enforces authentication. Embeddings are generated using a "
     "sentence-transformer model hosted on internal GPU nodes."),
    ("Engineering", 2, "Disaster Recovery and Failover Runbook",
     "Primary region failover to the secondary region is triggered "
     "automatically when health checks fail for 3 consecutive minutes. "
     "Recovery Point Objective is 5 minutes; Recovery Time Objective is 15 "
     "minutes. Failover drills are run quarterly with results logged."),
    ("Engineering", 3, "Production Database Credentials Rotation Runbook",
     "This restricted runbook documents the quarterly rotation procedure for "
     "production database credentials, including the HSM-backed key "
     "management steps and the emergency rollback plan in case of rotation "
     "failure. Access requires security-team approval."),
    ("Engineering", 3, "Security Vulnerability Report - Auth Service",
     "A critical vulnerability (CVSS 9.1) was identified in the legacy "
     "authentication service allowing token replay under specific timing "
     "conditions. This restricted report details the exploit path and the "
     "patch timeline; disclosure is limited to the security response team."),

    ("Legal", 1, "Standard NDA Template",
     "This mutual non-disclosure agreement template is approved for use with "
     "vendors and prospective partners. Any modifications to liability caps "
     "or term length require review from in-house counsel before signature."),
    ("Legal", 1, "Standard Contractor Agreement Template",
     "This template governs independent contractor engagements, clarifying "
     "IP assignment, confidentiality obligations, and the absence of an "
     "employment relationship. Engagements longer than 12 months require "
     "Legal review for potential misclassification risk."),
    ("Legal", 2, "Data Processing Agreement - EU Customers",
     "This agreement governs the processing of personal data for customers "
     "in the European Union in accordance with GDPR, including data "
     "residency commitments and the 72-hour breach notification requirement."),
    ("Legal", 2, "Open Source License Compliance Policy",
     "Engineering teams must run license scans before adopting new "
     "dependencies. Copyleft licenses such as AGPL require Legal review "
     "before use in any shipped product to avoid unintended disclosure "
     "obligations."),
    ("Legal", 3, "Pending Litigation Summary - Patent Dispute",
     "The company is named in a pending patent infringement suit filed by a "
     "competitor regarding vector-search indexing methods. Outside counsel "
     "estimates exposure between 2 and 8 million USD; this restricted "
     "summary is privileged and confidential attorney work product."),
    ("Legal", 3, "Regulatory Investigation - Data Retention Practices",
     "A regulator has opened an inquiry into the company's historical data "
     "retention practices for customer support transcripts. This restricted "
     "briefing is prepared for executive leadership and outside counsel "
     "only, pending the company's formal response."),

    ("Sales", 1, "Sales Playbook - Enterprise Outbound",
     "The outbound motion targets accounts with 500+ employees. Discovery "
     "calls should identify budget, decision timeline, and security "
     "requirements within the first two conversations before a technical "
     "demo is scheduled."),
    ("Sales", 1, "Competitive Positioning One-Pager",
     "Compared to legacy document search vendors, our RBAC-aware retrieval "
     "reduces data exposure risk while maintaining sub-second query latency. "
     "Use this positioning in competitive deals against incumbent providers."),
    ("Sales", 1, "Customer Onboarding Playbook",
     "New enterprise customers are assigned a dedicated onboarding manager "
     "for the first 90 days. Kickoff calls should be scheduled within 5 "
     "business days of contract signature, with a technical integration "
     "checklist shared in advance."),
    ("Sales", 2, "Enterprise Discount Approval Matrix",
     "Discounts above 20% require VP of Sales approval; discounts above 35% "
     "require CFO sign-off. Multi-year commitments may unlock an additional "
     "5% at the AE's discretion within standard deal desk guidelines."),

    ("Executive", 2, "Board Meeting Agenda - Q1 2026",
     "The agenda covers the Q1 financial review, the Project Northstar "
     "acquisition update, key engineering security incidents, and the "
     "proposed FY2027 headcount plan for board discussion and approval."),
    ("Executive", 3, "Strategic Plan 2026-2028 - Confidential Draft",
     "The three-year strategic plan outlines expansion into the European "
     "market, a targeted 40% revenue CAGR, and two potential acquisitions "
     "including Project Northstar. This restricted draft is for board and "
     "executive team review only ahead of the annual offsite."),
    ("Executive", 3, "CEO Succession Planning Memo",
     "This restricted memo outlines the board-approved succession framework "
     "for the CEO role, including internal candidate development plans and "
     "the external search contingency, to be discussed only in executive "
     "session."),
]

QUARTERS = ["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025", "Q1 2026", "Q2 2026"]

FINANCE_BUDGET_TEMPLATE = (
    "Total operating expenditure for {quarter} was {spend} million USD, "
    "{pct}% {direction} budget. Engineering accounted for {eng_pct}% of "
    "spend, primarily cloud infrastructure. {dept2} spend {dept2_change} "
    "{dept2_pct}% quarter over quarter{reason}."
)

SALES_PIPELINE_TEMPLATE = (
    "Strategic account pipeline for {quarter} stands at {pipeline} million "
    "USD in weighted value, with {deal_count} deals over 1 million USD in "
    "final procurement review. Win probability for the largest deal is "
    "estimated at {win_pct}%. {extra}"
)

ENG_INCIDENT_TEMPLATE = (
    "On {date}, {metric} on the {service} rose to {value} due to {cause}. "
    "The fix involved {fix}, {impact}."
)

SPRINT_NOTES_TEMPLATE = (
    "Sprint {sprint_num} for the {team} team focused on {focus}. "
    "{completed} story points were completed against a commitment of "
    "{committed}. Key blockers included {blocker}, which is being tracked "
    "as a follow-up for next sprint."
)

BOARD_UPDATE_TEMPLATE = (
    "The {quarter} board update highlights {headline}. Customer count grew "
    "to approximately {customers}, with net revenue retention at {nrr}%. "
    "The board {board_action} regarding {topic}."
)

random_services = [
    "query API", "document ingestion pipeline", "authentication service",
    "vector search cluster", "notification service", "billing service",
]
random_causes = [
    "an unbounded vector search without a metadata pre-filter",
    "a misconfigured autoscaling policy under peak load",
    "a slow downstream dependency timing out under retry storms",
    "a memory leak in the embedding cache",
    "a database connection pool exhaustion during a traffic spike",
]
random_fixes = [
    "adding mandatory RBAC filtering before the similarity search stage",
    "introducing a circuit breaker around the downstream dependency",
    "rightsizing the autoscaling thresholds and adding a warm pool",
    "patching the cache eviction logic and adding memory alerts",
    "increasing the connection pool size and adding backpressure",
]
random_metrics = ["p99 latency", "error rate", "average response time", "queue depth"]

sprint_teams = ["Retrieval Platform", "Identity & Access", "Data Ingestion", "Frontend", "Search Relevance"]
sprint_focuses = [
    "improving retrieval latency for large document sets",
    "hardening the RBAC filtering logic with additional test coverage",
    "migrating the embedding pipeline to a newer model version",
    "building the audit log dashboard for compliance review",
    "reducing false-positive access denials reported by beta customers",
]
sprint_blockers = [
    "a delayed API contract from the identity team",
    "flaky integration tests in the CI pipeline",
    "an unresolved dependency version conflict",
    "pending security review sign-off",
]


def slugify(title):
    return "".join(c.lower() if c.isalnum() else "-" for c in title).strip("-")


def generate_templated_docs():
    docs = []

    for q in QUARTERS:
        spend = round(random.uniform(3.2, 5.4), 1)
        pct = random.randint(2, 12)
        direction = random.choice(["under", "over"])
        eng_pct = random.randint(38, 55)
        dept2 = random.choice(["Marketing", "Sales", "Legal", "HR"])
        dept2_change = random.choice(["increased", "decreased"])
        dept2_pct = random.randint(4, 22)
        reason = random.choice([
            " due to the product launch campaign",
            " following headcount growth",
            " tied to a one-time vendor renewal",
            "",
        ])
        body = FINANCE_BUDGET_TEMPLATE.format(
            quarter=q, spend=spend, pct=pct, direction=direction,
            eng_pct=eng_pct, dept2=dept2, dept2_change=dept2_change,
            dept2_pct=dept2_pct, reason=reason,
        )
        docs.append(("Finance", 2, f"{q} Departmental Budget Summary", body))

    for q in QUARTERS:
        pipeline = round(random.uniform(9.0, 22.0), 1)
        deal_count = random.randint(1, 5)
        win_pct = random.randint(35, 80)
        extra = random.choice([
            "Two deals slipped from the prior quarter due to procurement delays.",
            "A new logo in the fintech vertical anchors the largest opportunity.",
            "Renewal risk on one strategic account is being actively managed.",
            "",
        ])
        body = SALES_PIPELINE_TEMPLATE.format(
            quarter=q, pipeline=pipeline, deal_count=deal_count,
            win_pct=win_pct, extra=extra,
        )
        docs.append(("Sales", 2, f"{q} Pipeline Review - Strategic Accounts", body))

    incident_months = ["January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October"]
    for month in incident_months:
        service = random.choice(random_services)
        metric = random.choice(random_metrics)
        cause = random.choice(random_causes)
        fix = random.choice(random_fixes)
        value = (f"{round(random.uniform(1.5, 6.0), 1)} seconds"
                  if "latency" in metric or "time" in metric
                  else f"{random.randint(2,18)}%")
        impact = random.choice([
            "reducing average result set size by 90%",
            "cutting p99 latency back under the 500ms SLO",
            "eliminating repeat occurrences over the following month",
            "restoring the service to its normal error budget",
        ])
        body = ENG_INCIDENT_TEMPLATE.format(
            date=f"{month} {random.randint(1,28)}", metric=metric, service=service,
            value=value, cause=cause, fix=fix, impact=impact,
        )
        docs.append(("Engineering", 2, f"Incident Postmortem - {service.title()} ({month})", body))

    for sprint_num in range(1, 9):
        team = random.choice(sprint_teams)
        focus = random.choice(sprint_focuses)
        committed = random.randint(30, 55)
        completed = committed - random.randint(0, 10)
        blocker = random.choice(sprint_blockers)
        body = SPRINT_NOTES_TEMPLATE.format(
            sprint_num=sprint_num, team=team, focus=focus,
            completed=completed, committed=committed, blocker=blocker,
        )
        docs.append(("Engineering", 1, f"Sprint {sprint_num} Notes - {team} Team", body))

    for q in QUARTERS:
        headline = random.choice([
            "strong enterprise pipeline growth",
            "improved gross margin from infrastructure optimization",
            "successful launch of the RBAC-aware retrieval product line",
            "continued expansion into the EU market",
        ])
        customers = random.randint(180, 340)
        nrr = random.randint(104, 128)
        board_action = random.choice([
            "approved additional budget", "requested a follow-up deep dive",
            "deferred a decision pending Q&A", "expressed support",
        ])
        topic = random.choice([
            "the Project Northstar acquisition", "European market expansion",
            "the FY2027 headcount plan", "the security incident response process",
        ])
        body = BOARD_UPDATE_TEMPLATE.format(
            quarter=q, headline=headline, customers=customers, nrr=nrr,
            board_action=board_action, topic=topic,
        )
        docs.append(("Executive", 3, f"Board Update Highlights - {q}", body))

    return docs


def main():
    all_docs = HAND_AUTHORED + generate_templated_docs()

    metadata = {}
    seen_slugs = {}
    for i, (dept, level, title, body) in enumerate(all_docs, start=1):
        base_slug = slugify(title)[:40]
        seen_slugs[base_slug] = seen_slugs.get(base_slug, 0) + 1
        suffix = "" if seen_slugs[base_slug] == 1 else f"-{seen_slugs[base_slug]}"
        doc_id = f"doc_{i:03d}_{base_slug}{suffix}"

        filepath = os.path.join(OUT_DIR, f"{doc_id}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Title: {title}\nDepartment: {dept}\n\n{body}\n")
        metadata[doc_id] = {
            "title": title,
            "department": dept,
            "confidentiality_level": level,
            "path": filepath.replace("\\", "/"),
        }

    # Keep documents that were uploaded through the UI - regenerating the
    # built-in dataset must not silently drop them from the index.
    meta_path = os.path.join("data", "metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                for doc_id, m in json.load(f).items():
                    if m.get("uploaded_by"):
                        metadata[doc_id] = m
        except (OSError, ValueError):
            pass

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Generated {len(metadata)} documents into {OUT_DIR}/")
    print("Metadata index written to data/metadata.json")

    from collections import Counter
    dept_counts = Counter(m["department"] for m in metadata.values())
    level_counts = Counter(m["confidentiality_level"] for m in metadata.values())
    print("By department:", dict(dept_counts))
    print("By confidentiality level:", dict(level_counts))


if __name__ == "__main__":
    main()
