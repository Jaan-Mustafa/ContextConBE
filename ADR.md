# ADR: StackShift Backend

## Status: Accepted

## Date: 2026-04-19

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Framework** | FastAPI (Python 3.11+) | Async, auto-docs, fast to build |
| **Database** | PostgreSQL on NeonDB | Serverless, free tier, zero infra |
| **ORM** | SQLAlchemy 2.0 (async) | Mature, async support with asyncpg |
| **Migrations** | Alembic | Standard SQLAlchemy migrations |
| **DB Driver** | asyncpg | High-performance async Postgres driver |
| **HTTP Client** | httpx (async) | Async requests to CrustData APIs |
| **AI/LLM** | Anthropic Python SDK | Claude API for stack parsing + outreach |
| **Validation** | Pydantic v2 | Request/response schemas (built into FastAPI) |
| **Server** | Uvicorn | ASGI server for FastAPI |
| **Env** | python-dotenv | Environment variable management |

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app, CORS, lifespan
│   ├── config.py                   # Settings from env vars
│   ├── database.py                 # SQLAlchemy engine, session factory
│   │
│   ├── models/                     # SQLAlchemy ORM models (DB tables)
│   │   ├── __init__.py
│   │   ├── user.py                 # users table
│   │   ├── customer.py             # customers table
│   │   ├── competitor.py           # competitors table
│   │   ├── competitor_customer.py  # competitor_customers table
│   │   ├── tracked_person.py       # tracked_people table
│   │   ├── signal.py               # signals table
│   │   └── outreach.py             # outreach_drafts table
│   │
│   ├── schemas/                    # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── onboard.py
│   │   ├── signal.py
│   │   ├── outreach.py
│   │   └── scan.py
│   │
│   ├── routers/                    # API endpoint handlers
│   │   ├── __init__.py
│   │   ├── onboard.py              # POST /api/onboard
│   │   ├── scan.py                 # POST /api/scan
│   │   ├── signals.py              # GET  /api/signals
│   │   ├── outreach.py             # POST /api/outreach
│   │   └── competitors.py          # GET  /api/competitors/customers
│   │
│   ├── services/                   # Business logic
│   │   ├── __init__.py
│   │   ├── crustdata.py            # CrustData API client
│   │   ├── claude.py               # Claude/Anthropic API client
│   │   ├── champion_tracker.py     # Flow 1: track champions
│   │   ├── competitor_analyzer.py  # Flow 2: analyze competitors
│   │   └── signal_scorer.py        # Scoring algorithm
│   │
│   └── utils/
│       ├── __init__.py
│       └── stack_parser.py         # Extract tech stack from job descriptions
│
├── alembic/
│   ├── env.py
│   └── versions/                   # Migration files
├── alembic.ini
├── requirements.txt
├── .env.example
└── Dockerfile                      # For deployment
```

---

## Database Schema (NeonDB - PostgreSQL)

### Tables

```sql
-- Users / Sales teams
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    product_description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Customer companies being tracked
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    crustdata_company_id VARCHAR(100),
    linkedin_url VARCHAR(500),
    industry VARCHAR(255),
    headcount INTEGER,
    revenue_lower BIGINT,
    revenue_upper BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Competitors being monitored
CREATE TABLE competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Competitor's discovered customers (from job description scanning)
CREATE TABLE competitor_customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id UUID REFERENCES competitors(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    crustdata_company_id VARCHAR(100),
    discovered_via VARCHAR(50) DEFAULT 'job_description',
    confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- People being tracked at customer/competitor companies
CREATE TABLE tracked_people (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crustdata_person_id VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    linkedin_url VARCHAR(500),
    current_company VARCHAR(255),
    current_company_id VARCHAR(100),
    previous_company VARCHAR(255),
    previous_company_id VARCHAR(100),
    transition_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    source VARCHAR(20),
    source_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Generated signals
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    person_id UUID REFERENCES tracked_people(id),
    type VARCHAR(30) NOT NULL,
    flow VARCHAR(30) NOT NULL,
    score INTEGER NOT NULL,
    urgency VARCHAR(10) NOT NULL,
    reasoning TEXT,
    suggested_action TEXT,
    target_company VARCHAR(255),
    target_company_size INTEGER,
    target_company_revenue_lower BIGINT,
    target_company_revenue_upper BIGINT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Generated outreach email drafts
CREATE TABLE outreach_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id) ON DELETE CASCADE,
    subject_line VARCHAR(500),
    email_body TEXT,
    talking_points JSONB,
    tone VARCHAR(30),
    timing_recommendation VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### ER Diagram

```
users
  │
  ├──1:N── customers
  │            │
  │            └──1:N── tracked_people (source='customer')
  │
  ├──1:N── competitors
  │            │
  │            └──1:N── competitor_customers
  │                         │
  │                         └──1:N── tracked_people (source='competitor_customer')
  │
  └──1:N── signals
               │
               ├── → tracked_people (person_id FK)
               │
               └──1:N── outreach_drafts
```

### Indexes

```sql
CREATE INDEX idx_customers_user_id ON customers(user_id);
CREATE INDEX idx_competitors_user_id ON competitors(user_id);
CREATE INDEX idx_tracked_people_status ON tracked_people(status);
CREATE INDEX idx_tracked_people_source ON tracked_people(source, source_id);
CREATE INDEX idx_signals_user_id ON signals(user_id);
CREATE INDEX idx_signals_type ON signals(type);
CREATE INDEX idx_signals_urgency ON signals(urgency);
CREATE INDEX idx_signals_score ON signals(score DESC);
CREATE INDEX idx_outreach_signal_id ON outreach_drafts(signal_id);
```

---

## API Endpoints

### POST /api/onboard
Onboard a new sales team with their product, customers, and competitors.

```python
# Request
{
    "email": "sales@datadog.com",
    "company_name": "Datadog",
    "product_name": "Datadog",
    "product_description": "Cloud monitoring and observability platform",
    "customers": [
        {"company_name": "Acme Corp", "linkedin_url": "linkedin.com/company/acme"},
        {"company_name": "BigCorp"}
    ],
    "competitors": [
        {"company_name": "New Relic", "product_name": "New Relic"},
        {"company_name": "Grafana Labs", "product_name": "Grafana"}
    ]
}

# Response 201
{
    "user_id": "uuid-here",
    "customers_tracked": 2,
    "competitors_tracked": 2,
    "message": "Onboarding complete. Run a scan to discover signals."
}
```

### POST /api/scan
Trigger a full scan — runs both Flow 1 (Champion Tracker) and Flow 2 (Competitor Analyzer).

```python
# Request
{"user_id": "uuid-here"}

# Response 200
{
    "scan_id": "uuid",
    "people_tracked": 47,
    "signals_generated": 5,
    "competitor_customers_discovered": 12,
    "breakdown": {
        "new_leads": 2,
        "churn_risks": 1,
        "competitive_displacements": 2
    },
    "duration_seconds": 8.3
}
```

### GET /api/signals
Fetch ranked signals with filters.

```python
# Query params
?user_id=uuid
&type=new_lead|churn_risk|competitive_displacement  (optional)
&flow=champion_tracker|competitor_analyzer           (optional)
&urgency=hot|warm|cool                               (optional)
&sort=score|date                                     (optional, default: score)
&limit=20                                            (optional)
&offset=0                                            (optional)

# Response 200
{
    "signals": [
        {
            "id": "uuid",
            "type": "new_lead",
            "flow": "champion_tracker",
            "person": {
                "name": "Sarah Chen",
                "title": "CTO",
                "linkedin_url": "linkedin.com/in/sarahchen",
                "previous_company": "Acme Corp",
                "new_company": "Zeta Inc",
                "transition_date": "2026-04-01",
                "days_since_transition": 18
            },
            "target_company": {
                "name": "Zeta Inc",
                "size": 450,
                "revenue": {"lower": 50000000, "upper": 100000000},
                "industry": "SaaS"
            },
            "score": 91,
            "urgency": "hot",
            "reasoning": "Sarah used Datadog for 3 years at Acme Corp. She led the migration from New Relic to Datadog in 2024. As CTO at Zeta, she has full tooling authority. Zeta has no observability vendor in job postings.",
            "suggested_action": "Send warm reconnect email within 7 days. Reference her Acme experience. Offer POC.",
            "is_read": false,
            "created_at": "2026-04-19T10:30:00Z"
        }
    ],
    "total": 5,
    "filters_applied": {"type": null, "urgency": null}
}
```

### GET /api/signals/:id
Get full detail for a single signal.

```python
# Response 200
{
    "id": "uuid",
    "type": "new_lead",
    "flow": "champion_tracker",
    "person": { ... },
    "target_company": { ... },
    "source_company": { ... },
    "score": 91,
    "score_breakdown": {
        "seniority": 30,
        "recency": 20,
        "company_size": 16,
        "familiarity": 15,
        "budget": 10
    },
    "urgency": "hot",
    "reasoning": "...",
    "suggested_action": "...",
    "outreach_draft": null
}
```

### POST /api/outreach
Generate a personalized outreach email for a signal.

```python
# Request
{"signal_id": "uuid"}

# Response 200
{
    "id": "uuid",
    "signal_id": "uuid",
    "subject_line": "Congrats on the CTO role at Zeta, Sarah!",
    "email_body": "Hi Sarah,\n\nCongratulations on your move to Zeta as CTO...",
    "talking_points": [
        "She led the New Relic to Datadog migration at Acme in 2024",
        "Zeta has no observability vendor yet — greenfield opportunity",
        "Zeta is growing 12% QoQ — they need monitoring now",
        "Offer POC + team onboarding support"
    ],
    "tone": "warm_reconnect",
    "timing_recommendation": "Send within 7 days — she's still building her stack"
}
```

### GET /api/competitors/customers
List discovered customers of tracked competitors.

```python
# Query params
?user_id=uuid

# Response 200
{
    "competitors": [
        {
            "name": "New Relic",
            "product_name": "New Relic",
            "discovered_customers": [
                {
                    "company_name": "MegaCorp",
                    "confidence": 0.92,
                    "discovered_via": "job_description",
                    "evidence": "3 job postings mention 'New Relic experience required'"
                }
            ],
            "total_customers_found": 12
        }
    ]
}
```

---

## Service Layer Detail

### crustdata.py — CrustData API Client

```python
class CrustDataClient:
    BASE_URL = "https://api.crustdata.com"

    async def search_people(
        self,
        company_name: str,
        title_filter: list[str] = ["CTO", "VP", "Director", "Head"]
    ) -> list[Person]:
        """Find senior people at a company."""

    async def get_person(self, person_id: str) -> PersonDetail:
        """Get full profile with employment history."""

    async def get_company(self, company_id: str) -> CompanyDetail:
        """Get company details (revenue, headcount, industry)."""

    async def search_jobs(
        self,
        company_name: str = None,
        description_contains: str = None
    ) -> list[JobListing]:
        """Search job listings, optionally filtering by description text."""

    async def detect_transitions(
        self,
        people: list[Person],
        since_days: int = 90
    ) -> list[Transition]:
        """Compare current vs past employment to find recent transitions."""
```

### champion_tracker.py — Flow 1

```python
class ChampionTracker:
    """
    Flow 1: Track champions at customer companies.

    1. For each customer company, fetch senior people (VP+)
    2. Store them as tracked_people
    3. Detect departures (person's current company != customer company)
    4. For departed people:
       a. Find their new company
       b. Generate NEW_LEAD signal (opportunity at new company)
       c. Generate CHURN_RISK signal (risk at old customer)
    """

    async def scan(self, user_id: str, customers: list[Customer]) -> list[Signal]:
        for customer in customers:
            # 1. Find senior people at this customer
            people = await crustdata.search_people(
                company_name=customer.company_name,
                title_filter=["CTO", "VP", "Director", "Head"]
            )

            # 2. Check each person's employment history
            for person in people:
                if person.current_company != customer.company_name:
                    # Person has LEFT this customer company

                    # Signal A: New lead at their new company
                    new_lead = Signal(
                        type="new_lead",
                        flow="champion_tracker",
                        person=person,
                        target_company=person.current_company,
                        reasoning=await claude.analyze_opportunity(person, customer)
                    )

                    # Signal B: Churn risk at old customer
                    churn_risk = Signal(
                        type="churn_risk",
                        flow="champion_tracker",
                        person=person,
                        target_company=customer.company_name,
                        reasoning=await claude.analyze_churn_risk(person, customer)
                    )

                    signals.extend([new_lead, churn_risk])

        return signals
```

### competitor_analyzer.py — Flow 2

```python
class CompetitorAnalyzer:
    """
    Flow 2: Find competitor's customers and track their leadership changes.

    1. Search job descriptions for competitor product mentions
    2. Identify companies using competitor's product
    3. Track leadership transitions at those companies
    4. When a new leader joins from a company that used YOUR product:
       → Generate COMPETITIVE_DISPLACEMENT signal
    """

    async def discover_customers(self, competitor: Competitor) -> list[CompetitorCustomer]:
        # Search job listings for "experience with [competitor product]"
        jobs = await crustdata.search_jobs(
            description_contains=competitor.product_name
        )

        # Extract unique companies from matching jobs
        # Use Claude to validate: is this company actually using the competitor?
        companies = await claude.validate_competitor_customers(jobs, competitor)
        return companies

    async def scan(
        self,
        user: User,
        competitor_customers: list[CompetitorCustomer]
    ) -> list[Signal]:
        for comp_customer in competitor_customers:
            # Find leadership transitions at competitor's customers
            people = await crustdata.search_people(comp_customer.company_name)

            for person in people:
                # Check: did this person come from a company that uses OUR product?
                prev_company_jobs = await crustdata.search_jobs(
                    company_name=person.previous_company,
                    description_contains=user.product_name
                )

                if prev_company_jobs:
                    # This person used OUR product at their old company
                    # Now they're at a COMPETITOR's customer
                    # → Displacement opportunity!
                    signal = Signal(
                        type="competitive_displacement",
                        flow="competitor_analyzer",
                        person=person,
                        target_company=comp_customer.company_name,
                        reasoning=await claude.analyze_displacement(
                            person, user.product_name, competitor.product_name
                        )
                    )
                    signals.append(signal)

        return signals
```

### signal_scorer.py — Scoring Algorithm

```python
def calculate_score(signal: Signal) -> int:
    score = 0.0

    # Seniority (30%)
    seniority_scores = {
        "CTO": 100, "CEO": 100, "Co-founder": 100,
        "VP": 80, "Vice President": 80,
        "Director": 60,
        "Head": 50, "Head of": 50,
        "Senior Manager": 30, "Manager": 20
    }
    title = signal.person.title
    seniority = next(
        (v for k, v in seniority_scores.items() if k.lower() in title.lower()),
        20
    )
    score += seniority * 0.30

    # Recency (25%)
    days = signal.person.days_since_transition
    if days < 14:
        recency = 100
    elif days < 30:
        recency = 80
    elif days < 60:
        recency = 50
    elif days < 90:
        recency = 30
    else:
        recency = 10
    score += recency * 0.25

    # Company size (20%)
    headcount = signal.target_company_size or 0
    if headcount > 1000:
        size = 100
    elif headcount > 500:
        size = 80
    elif headcount > 100:
        size = 60
    elif headcount > 50:
        size = 40
    else:
        size = 20
    score += size * 0.20

    # Familiarity with product (15%)
    if signal.person_used_product_directly:
        familiarity = 100
    elif signal.team_used_product:
        familiarity = 70
    elif signal.company_used_product:
        familiarity = 40
    else:
        familiarity = 10
    score += familiarity * 0.15

    # Budget signal (10%)
    if signal.company_raised_recently:
        budget = 100
    elif signal.revenue_growing:
        budget = 70
    elif signal.headcount_growing:
        budget = 50
    else:
        budget = 20
    score += budget * 0.10

    return round(score)


def calculate_urgency(score: int, days: int) -> str:
    if score >= 80 and days < 30:
        return "hot"
    elif score >= 50 or days < 60:
        return "warm"
    return "cool"
```

### claude.py — LLM Client

```python
class ClaudeClient:
    """Claude API for analysis and content generation."""

    async def extract_tech_stack(self, job_descriptions: list[str]) -> list[Tool]:
        """Parse job descriptions to extract tools/vendors mentioned."""

    async def analyze_opportunity(
        self, person: Person, source_customer: Customer
    ) -> str:
        """Generate reasoning for a new_lead signal."""

    async def analyze_churn_risk(
        self, person: Person, customer: Customer
    ) -> str:
        """Generate reasoning for a churn_risk signal."""

    async def analyze_displacement(
        self, person: Person, our_product: str, competitor_product: str
    ) -> str:
        """Generate reasoning for a competitive_displacement signal."""

    async def generate_outreach(
        self, signal: Signal, user: User
    ) -> OutreachDraft:
        """Generate personalized outreach email + talking points."""

    async def validate_competitor_customers(
        self, jobs: list[JobListing], competitor: Competitor
    ) -> list[CompetitorCustomer]:
        """Validate if job listings indicate actual product usage."""
```

---

## Request/Response Flow

```
Frontend                    Backend                     External
  │                           │                           │
  │  POST /api/onboard        │                           │
  │ ─────────────────────►    │                           │
  │                           │  INSERT users, customers, │
  │                           │  competitors into NeonDB  │
  │                           │ ──────────────────────►   │
  │   { user_id }             │                           │
  │ ◄─────────────────────    │                           │
  │                           │                           │
  │  POST /api/scan           │                           │
  │ ─────────────────────►    │                           │
  │                           │  CrustData: search_people │
  │                           │ ──────────────────────►   │
  │                           │  ◄──────────────────────  │
  │                           │                           │
  │                           │  CrustData: search_jobs   │
  │                           │ ──────────────────────►   │
  │                           │  ◄──────────────────────  │
  │                           │                           │
  │                           │  Claude: analyze signals  │
  │                           │ ──────────────────────►   │
  │                           │  ◄──────────────────────  │
  │                           │                           │
  │                           │  Score + store signals    │
  │                           │  in NeonDB               │
  │   { signals_found: 5 }    │                           │
  │ ◄─────────────────────    │                           │
  │                           │                           │
  │  GET /api/signals         │                           │
  │ ─────────────────────►    │                           │
  │                           │  SELECT from NeonDB       │
  │   { signals: [...] }      │                           │
  │ ◄─────────────────────    │                           │
  │                           │                           │
  │  POST /api/outreach       │                           │
  │ ─────────────────────►    │                           │
  │                           │  Claude: generate email   │
  │                           │ ──────────────────────►   │
  │                           │  ◄──────────────────────  │
  │   { email, talking_pts }  │                           │
  │ ◄─────────────────────    │                           │
```

---

## Environment Variables

```env
# backend/.env.example

# NeonDB
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/stackshift?sslmode=require

# CrustData
CRUSTDATA_API_KEY=your_key
CRUSTDATA_BASE_URL=https://api.crustdata.com

# Anthropic
ANTHROPIC_API_KEY=your_key

# App
CORS_ORIGINS=http://localhost:5173
APP_ENV=development
```

---

## requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.0
anthropic==0.40.0
httpx==0.27.0
pydantic==2.9.0
pydantic-settings==2.5.0
python-dotenv==1.0.1
```

---

## Build Priority (Hackathon)

| Priority | Module | Why |
|----------|--------|-----|
| P0 | `main.py` + `config.py` + `database.py` | App skeleton |
| P0 | `models/` + Alembic migration | DB must exist |
| P0 | `crustdata.py` | Core data source |
| P0 | `champion_tracker.py` | Flow 1 = primary demo |
| P0 | `routers/onboard.py` + `routers/scan.py` + `routers/signals.py` | Core API |
| P1 | `claude.py` + outreach generation | Key demo moment |
| P1 | `signal_scorer.py` | Makes signals ranked |
| P1 | `competitor_analyzer.py` | Flow 2 = stretch demo |
| P2 | `routers/competitors.py` | Nice to have |
| P2 | Dockerfile | Deploy only if time |
