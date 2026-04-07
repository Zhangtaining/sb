# SmartGym AI — Business Plan Brief for Manus

> **Instructions for Manus:** Use this brief to generate a professional, investor-ready business plan document. The format should include an executive summary, market analysis, product description, go-to-market strategy, business model, financial projections, competitive landscape, team requirements, and risk analysis. Tone should be confident, data-driven, and compelling to both investors and potential gym operator customers.

---

## 1. Company Overview

**Company Name:** SmartGym AI (working title)

**Tagline:** *AI-powered coaching, built for every gym.*

**Business Type:** B2B SaaS — sold to gym operators (gyms, fitness studios, hotel fitness centers, corporate wellness facilities)

**Mission:** Transform every gym into a world-class coaching environment by deploying real-time AI that watches, understands, and coaches every member — without hiring more staff.

**Stage:** MVP / early-stage product with working prototype (Phase 1 complete, Phase 2 in progress)

---

## 2. The Problem

Gym operators face a coaching gap: most members exercise without guidance, leading to poor form, slow results, injury, and churn. Hiring enough qualified personal trainers to serve every member simultaneously is cost-prohibitive. Wearables and fitness apps help outside the gym but cannot see what a person is actually doing during a workout.

**Key pain points for gym owners:**
- Member churn is high (average gym loses ~50% of members within 6 months)
- Trainer-to-member ratio is inadequate for most budget and mid-market gyms (1 trainer per 50–100 members)
- Operators have no visibility into what exercises members are actually performing
- Form-related injuries create liability and negative word-of-mouth
- Differentiation is difficult — most gyms offer the same equipment and group classes

---

## 3. The Solution

SmartGym AI is a multi-camera AI system installed in a gym that:

1. **Sees every member in real time** using computer vision (cameras + GPU edge server)
2. **Understands what they are doing** — identifies the exercise, counts reps, and measures form quality using pose estimation and an AI classifier
3. **Delivers personalized coaching** to each member's phone via an AI trainer that speaks to them through their earphones
4. **Knows who each person is** via face recognition and biometric identity matching (opt-in), enabling truly personalized advice
5. **Conducts full AI coaching conversations** — members can ask the AI trainer questions mid-workout, get workout plans, and track their progress

The result: every gym member gets an experience close to having a personal trainer, at no additional per-member labor cost to the gym.

---

## 4. Product Description

### 4.1 Hardware Component (on-premise)
- 2–8 standard IP cameras covering the gym floor (customer-supplied or bundled)
- 1 edge GPU server (e.g., NVIDIA RTX 4090 workstation) installed on-site, running the full AI pipeline locally for privacy and low latency
- Optional: in-gym display screens (kiosk mode) showing floor map and motivational stats

### 4.2 AI Pipeline (the core technology)
- **Computer Vision:** YOLOv11 person detection + MediaPipe pose estimation at 15 FPS per camera
- **Exercise Recognition:** AI classifier (Temporal Convolutional Network on 3D pose keypoints) identifies 20+ gym exercises with >85% accuracy
- **Rep Counting & Form Analysis:** Per-member state machine tracking joint angles; detects common mistakes (e.g., knee cave in squats, elbow flare in bench press)
- **Person Identity:** Opt-in face recognition (InsightFace/ArcFace) and appearance-based re-identification (OSNet) links anonymous tracks to member profiles; works across all cameras simultaneously
- **Cross-Camera Tracking:** Homography-based floor mapping tracks members as they move throughout the facility

### 4.3 AI Coaching Engine
- Powered by Claude claude-sonnet-4-6 (Anthropic) via cloud API
- Retrieval-Augmented Generation (RAG) over a gym knowledge base (exercise science, form guides, safety guidelines)
- Personalized system prompts incorporating member's name, goals, workout history, and known injuries
- Capabilities:
  - Real-time form corrections delivered as spoken audio to the member's earphones
  - Session onboarding conversation: AI greets the member, asks about today's goals, and recommends a workout plan
  - Mid-workout Q&A: members can ask questions by voice or text
  - Progress tracking and motivational milestones
  - Weight/intensity adjustment advice based on rep history
  - Rest timer guidance and set completion summaries

### 4.4 Member Mobile App (iOS + Android)
- **Live Coaching tab:** Real-time AI voice guidance via earphones; rep counter and form score display
- **Chat tab:** Full conversational interface with the AI trainer (voice + text)
- **Stats tab:** Session summary, rep counts, form score per set, personal bests
- **Replay tab:** Short video clips of form issues with AI-generated timestamped notes
- **History tab:** Calendar heatmap, workout frequency, exercise progression charts

### 4.5 Gym Operator Dashboard (web)
- Live floor map: see where all active members are and what they are doing
- Aggregate analytics: popular equipment, peak hours, exercise distribution
- Member engagement metrics: session frequency, AI interaction rates
- Alert log: form injury risk flags, fall detection alerts (Phase 4)
- Member management and enrollment

---

## 5. Technology Differentiation

| Capability | SmartGym AI | Wearables (Apple Watch, Whoop) | Mirror / Tonal / Peloton | Generic Gym Apps |
|---|---|---|---|---|
| Sees actual gym equipment usage | Yes | No | No (home only) | No |
| Works for all gym members simultaneously | Yes | No (1 device per person) | No | No |
| Real-time voice coaching during workout | Yes | No | Yes (but scripted) | No |
| Personalized AI conversation (open-ended) | Yes | No | No | Limited |
| No behavior change required from member | Yes | No (must wear device) | No | No |
| Operator analytics dashboard | Yes | No | No | Limited |
| Installed in existing gym | Yes | N/A | No | N/A |

**Key moat:** The combination of real-time multi-person pose analysis, cross-camera identity tracking, and a personalized LLM coaching layer running simultaneously for all members in a physical gym is technically novel and difficult to replicate quickly.

---

## 6. Market Opportunity

### Total Addressable Market (TAM)
- Global gym and fitness club industry: ~$100B+ annual revenue (2024)
- Estimated 200,000+ commercial gym facilities globally
- AI fitness technology market projected to reach $15B+ by 2030

### Serviceable Addressable Market (SAM)
- Mid-market and premium gyms with 500–5,000 sq ft floor space and 200–2,000 active members
- Technology-forward gym operators already investing in digital member experience
- Estimated 30,000–50,000 such facilities in North America, Europe, and ANZ

### Serviceable Obtainable Market (SOM) — Year 1–3 Target
- 100 pilot gyms in Year 1; 500 gyms by end of Year 2; 2,000+ by Year 3
- Focus: boutique fitness studios, independent premium gyms, hotel fitness centers, corporate wellness centers

---

## 7. Business Model

### Pricing Structure (B2B SaaS + Hardware)

**Option A — SaaS Subscription (hardware sold separately or customer-supplied)**
| Tier | Monthly Fee | Features |
|---|---|---|
| Starter | $499/month | Up to 2 cameras, 200 active members, core coaching |
| Growth | $999/month | Up to 6 cameras, 800 active members, full identity + personalization |
| Enterprise | $2,499+/month | Unlimited cameras, multi-location, API access, white-label app |

**Option B — Hardware + SaaS Bundle**
- One-time hardware bundle (GPU server + cameras): $8,000–$15,000
- Ongoing SaaS subscription: 20–30% lower monthly rate than Option A

**Additional Revenue Streams:**
- Professional installation and onboarding: $1,500–$3,000 per site
- Custom exercise library additions: $500+ per batch
- White-label member app (branded for the gym): $300/month add-on
- Annual pre-pay discount: 15% off

### Unit Economics (Illustrative)
- Average Contract Value (ACV): ~$12,000/year (Growth tier)
- Hardware gross margin: ~40%
- SaaS gross margin: ~70–75%
- Blended CAC (direct sales + channel): ~$3,000–$5,000 per gym
- Estimated payback period: 4–6 months
- Net Revenue Retention target: 110%+ (expansion via tier upgrades and multi-location)

---

## 8. Go-to-Market Strategy

### Phase 1 — Lighthouse Customers (Months 1–6)
- Target: 5–10 hand-selected premium gyms in one metro market (e.g., Sydney or San Francisco)
- Offer: heavily subsidized or free pilot in exchange for testimonials, usage data, and referrals
- Goal: validate product-market fit, refine installation process, build case studies

### Phase 2 — Direct Sales + Inbound (Months 6–18)
- Hire 2 enterprise sales reps focused on independent gym owners and boutique studio chains
- Content marketing: case studies, ROI calculators ("reduce churn by X% = $Y/year")
- Presence at fitness industry trade shows (IHRSA, Fitness Australia, FIBO)
- Partner with gym management software vendors (Mindbody, ClubReady, Glofox) for referral integrations

### Phase 3 — Channel & Scale (Months 18–36)
- Channel partnerships with gym fit-out and AV installation companies
- Franchise gym group deals (e.g., F45, Anytime Fitness, Orangetheory) — single contract, multi-location rollout
- Geographic expansion: UK, Canada, Singapore, UAE

### Key Selling Points for Gym Owners
1. **Reduce member churn** — members who get results stay. AI coaching drives results.
2. **Differentiate from competitors** — "AI personal trainer included" is a compelling membership marketing message
3. **No extra staff cost** — the AI scales to every member simultaneously
4. **Operator visibility** — finally know what equipment members use and when
5. **Safety** — reduce liability from form injuries; optional fall detection alert

---

## 9. Competitive Landscape

| Competitor | Description | Weakness vs. SmartGym AI |
|---|---|---|
| Tonal / Mirror / iFIT | AI coaching hardware for home use | Cannot be installed in commercial gyms; requires equipment replacement |
| Kemtai / Sency | Computer vision rep counting via phone camera | Single-user, phone-only; no multi-camera; limited gym deployment |
| Vald Performance | Athlete performance tracking for elite sports | Priced for pro sports teams ($50k+); not for commercial gyms |
| Fitness AI / Hevy | Workout logging apps with AI plan generation | Cannot see the user; manual logging only |
| OpenFit / Future | Virtual coaching subscriptions | Remote coach, not real-time in-gym; no computer vision |

**SmartGym AI's unique position:** The only end-to-end, real-time, in-gym computer vision + LLM coaching platform built specifically for commercial gym operators as a B2B SaaS product.

---

## 10. Product Roadmap

| Phase | Timeline | Key Milestones |
|---|---|---|
| Phase 1 (MVP) | Complete | Single-camera rep counting, form alerts, real-time AI voice coaching, mobile app |
| Phase 2 (Identity) | In progress | Face recognition, personalized coaching, session onboarding conversation, workout planning |
| Phase 3 (Multi-camera) | Months 6–12 | Floor-plan tracking, ML exercise classifier, RAG knowledge base, kiosk displays |
| Phase 4 (Scale) | Months 12–24 | Kafka event bus, Kubernetes, TensorRT GPU optimization, fall detection, GDPR framework, multi-location |
| Phase 5 (Ecosystem) | Months 24+ | Gym management system integrations, franchise portal, third-party developer API, predictive churn model |

---

## 11. Team Requirements

*(To be filled in with actual founding team — structure below is a recommendation)*

- **CEO / Founder** — Gym industry domain knowledge + B2B sales
- **CTO / Co-Founder** — Computer vision and ML systems (current lead engineer)
- **Head of AI / ML** — LLM systems, RAG, model fine-tuning
- **Head of Sales** — Enterprise B2B, fitness vertical experience
- **Head of Customer Success** — Gym onboarding, training, retention

---

## 12. Financial Projections (Illustrative — to be validated)

| Year | Gyms | ARR | Headcount |
|---|---|---|---|
| Year 1 | 50 | $600K | 5 |
| Year 2 | 250 | $3M | 15 |
| Year 3 | 800 | $10M | 40 |
| Year 4 | 2,000 | $25M | 90 |

*Assumptions: Average ACV $12K, 10% annual churn, 20% expansion revenue, blended gross margin 65%*

---

## 13. Funding Ask

*(To be tailored based on actual raise target)*

**Seed Round Target:** $2–3M USD

**Use of Funds:**
- Product development (Phase 2–3 completion): 40%
- Sales & marketing (2 enterprise reps, trade shows, content): 30%
- Infrastructure & operations (GPU servers for pilots, cloud costs): 15%
- Team (key hires: sales, customer success): 15%

**12-Month Milestones with Funding:**
- 50 paying gyms live
- Phase 3 (multi-camera + ML classifier) shipped
- Signed LOI or pilot with one national gym franchise
- ARR $600K+

---

## 14. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| AI coaching accuracy (wrong form correction) | Conservative threshold tuning; fallback to pre-written template corrections; human trainer review mode |
| Privacy / biometric data regulations (GDPR, CCPA) | Opt-in only for identity features; encrypted biometric storage; one-click data deletion; legal review per market |
| Hardware installation complexity | Standardized installation kit; certified partner installer network; remote setup support |
| LLM API cost scaling with users | Rate-limiting per member; template caching for common corrections; explore on-premise LLM in Phase 4 |
| Competitor replication by large fitness tech | 18–24 month technical lead; gym operator relationships; data flywheel (model improves with more gym-specific data) |
| Gym owner sales cycle length (3–9 months) | Pilot-first model with low friction; ROI calculator tools; channel partner referrals to warm leads |

---

## 15. Vision

In 5 years, SmartGym AI is the default coaching layer in 10,000+ commercial gyms across 20 countries. Every gym member — regardless of budget — has access to real-time, personalized AI coaching. Gym operators see measurably lower churn, higher membership value, and a new competitive differentiator.

The long-term data flywheel: as the platform processes hundreds of millions of exercise sets, SmartGym AI's models become uniquely accurate at predicting injury risk, identifying optimal training loads, and personalizing programming — data no wearable or home fitness app can match.

---

*This brief was generated from the SmartGym AI technical design document and implementation plan. Financials are illustrative and require validation with actual business data.*
