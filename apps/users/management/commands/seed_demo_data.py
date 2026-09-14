from django.core.management.base import BaseCommand
from apps.users.models import User, University, Organization
from apps.issues.models import Issue, Adoption, StudentNomination
from apps.pitches.models import Pitch, CommunityFeedback, ProjectLifecycle
from apps.engagements.models import IndustryEngagement

class Command(BaseCommand):
    help = "Seed rich real-world demo data for Confluence platform"

    def handle(self, *args, **options):
        self.stdout.write("Seeding comprehensive real demo data...")

        # 1. Universities
        bit, _ = University.objects.get_or_create(
            name="Birsa Institute of Technology (BIT) Sindri",
            defaults={"code": "BITS-DHN", "district": "Dhanbad"}
        )
        nit, _ = University.objects.get_or_create(
            name="National Institute of Technology (NIT) Jamshedpur",
            defaults={"code": "NIT-JSR", "district": "East Singhbhum"}
        )
        ru, _ = University.objects.get_or_create(
            name="Ranchi University",
            defaults={"code": "RU-RNC", "district": "Ranchi"}
        )
        bau, _ = University.objects.get_or_create(
            name="Birsa Agricultural University",
            defaults={"code": "BAU-RNC", "district": "Ranchi"}
        )
        ku, _ = University.objects.get_or_create(
            name="Kolhan University",
            defaults={"code": "KU-CBS", "district": "West Singhbhum"}
        )

        # 2. Industry Organizations
        tata, _ = Organization.objects.get_or_create(
            name="Tata Steel Foundation & CSR",
            defaults={"org_type": "csr", "website": "https://www.tatasteel.com"}
        )
        cil, _ = Organization.objects.get_or_create(
            name="Central Coalfields Limited (CSR)",
            defaults={"org_type": "industry", "website": "https://www.centralcoalfields.in"}
        )
        agtech, _ = Organization.objects.get_or_create(
            name="Chotanagpur AgTech Innovations (MSME)",
            defaults={"org_type": "msme", "website": "https://chotanagpur-agtech.in"}
        )
        jindal, _ = Organization.objects.get_or_create(
            name="Jindal Steel & Power CSR Foundation",
            defaults={"org_type": "csr", "website": "https://www.jindalsteelpower.com"}
        )

        # 3. Users
        pwd = "Password@123"

        # Gov Admin
        admin_user, _ = User.objects.get_or_create(
            email="admin@jharkhand.gov.in",
            defaults={"name": "Director HTE (Gov Admin)", "role": User.Role.GOV_ADMIN, "is_staff": True, "is_superuser": True}
        )
        admin_user.set_password(pwd)
        admin_user.save()

        # Citizens
        citizen1, _ = User.objects.get_or_create(
            email="citizen@jharkhand.in",
            defaults={"name": "Rameshwar Munda", "role": User.Role.CITIZEN, "phone": "+91 94311 22334"}
        )
        citizen1.set_password(pwd)
        citizen1.save()

        citizen2, _ = User.objects.get_or_create(
            email="sunita.devi@jharkhand.in",
            defaults={"name": "Sunita Devi (Anganwadi Worker)", "role": User.Role.CITIZEN, "phone": "+91 94311 88221"}
        )
        citizen2.set_password(pwd)
        citizen2.save()

        citizen3, _ = User.objects.get_or_create(
            email="birsa.topno@jharkhand.in",
            defaults={"name": "Birsa Topno (Kisan Pradhan)", "role": User.Role.CITIZEN, "phone": "+91 94311 77119"}
        )
        citizen3.set_password(pwd)
        citizen3.save()

        # University Coordinators & Faculty Mentors
        coord_bit, _ = User.objects.get_or_create(
            email="coordinator@bitsindri.ac.in",
            defaults={"name": "Prof. S. Soren", "role": User.Role.UNIVERSITY_COORDINATOR, "university": bit, "phone": "+91 94311 55667"}
        )
        coord_bit.set_password(pwd)
        coord_bit.save()

        mentor_bit, _ = User.objects.get_or_create(
            email="mentor@bitsindri.ac.in",
            defaults={"name": "Dr. A. K. Singh (Civil & Env)", "role": User.Role.FACULTY_MENTOR, "university": bit}
        )
        mentor_bit.set_password(pwd)
        mentor_bit.save()

        coord_nit, _ = User.objects.get_or_create(
            email="coord.nit@nitjsr.ac.in",
            defaults={"name": "Dr. Rajesh Patnaik (Metallurgy)", "role": User.Role.UNIVERSITY_COORDINATOR, "university": nit, "phone": "+91 94311 44332"}
        )
        coord_nit.set_password(pwd)
        coord_nit.save()

        mentor_bau, _ = User.objects.get_or_create(
            email="mentor.agri@bau.ac.in",
            defaults={"name": "Dr. P. Mishra (Biosystems & Hort)", "role": User.Role.FACULTY_MENTOR, "university": bau}
        )
        mentor_bau.set_password(pwd)
        mentor_bau.save()

        # Students
        student1, _ = User.objects.get_or_create(
            email="student1@bitsindri.ac.in",
            defaults={"name": "Priya Sharma", "role": User.Role.STUDENT, "university": bit}
        )
        student1.set_password(pwd)
        student1.save()

        student2, _ = User.objects.get_or_create(
            email="student2@bitsindri.ac.in",
            defaults={"name": "Amit Kumar Mahto", "role": User.Role.STUDENT, "university": bit}
        )
        student2.set_password(pwd)
        student2.save()

        student_nit, _ = User.objects.get_or_create(
            email="student.nit@nitjsr.ac.in",
            defaults={"name": "Rahul Verma", "role": User.Role.STUDENT, "university": nit}
        )
        student_nit.set_password(pwd)
        student_nit.save()

        student_bau, _ = User.objects.get_or_create(
            email="student.bau@bau.ac.in",
            defaults={"name": "Ananya Das", "role": User.Role.STUDENT, "university": bau}
        )
        student_bau.set_password(pwd)
        student_bau.save()

        # Industry Partners
        industry_tata, _ = User.objects.get_or_create(
            email="csr@tatasteel.com",
            defaults={"name": "Vikram Sengupta", "role": User.Role.INDUSTRY_PARTNER, "organization": tata}
        )
        industry_tata.set_password(pwd)
        industry_tata.save()

        industry_cil, _ = User.objects.get_or_create(
            email="csr@centralcoalfields.in",
            defaults={"name": "Manoj Kumar (GM CSR)", "role": User.Role.INDUSTRY_PARTNER, "organization": cil}
        )
        industry_cil.set_password(pwd)
        industry_cil.save()

        industry_agtech, _ = User.objects.get_or_create(
            email="innovate@chotanagpur-agtech.in",
            defaults={"name": "Dr. Rakesh Singh (Founder)", "role": User.Role.INDUSTRY_PARTNER, "organization": agtech}
        )
        industry_agtech.set_password(pwd)
        industry_agtech.save()

        # 4. Societal Issues (10 challenges across Jharkhand)
        issue1, _ = Issue.objects.get_or_create(
            title="High Fluoride and Coliform Contamination in Topchanchi Rural Water Supply",
            defaults={
                "description": "Over 4 village clusters in Topchanchi block face severe fluorosis and gastrointestinal distress due to contaminated ground aquifers and failing hand pumps. Women travel 3 km daily for potable water.",
                "expected_outcome": "Low-cost decentralized community solar filtration unit capable of removing fluoride < 1.0 ppm and pathogens, maintained by village Jal Sahiya committee.",
                "district": "Dhanbad",
                "latitude": 23.9056,
                "longitude": 86.2084,
                "category": Issue.Category.WATER,
                "photo_url": "https://images.unsplash.com/photo-1541888946425-d0fbb186c5f8?w=800",
                "status": Issue.Status.ADOPTED,
                "submitted_by": citizen1,
                "ai_confidence": 0.94,
                "ai_triage_notes": "Triaged: High priority water quality issue with epidemiological impact."
            }
        )

        Adoption.objects.get_or_create(
            issue=issue1,
            defaults={
                "university": bit,
                "mode": Adoption.Mode.SELF_ADOPTED
            }
        )

        issue2, _ = Issue.objects.get_or_create(
            title="Post-Harvest Tomato & Chayote Spoilage in Tamar Tribal Green Belt",
            defaults={
                "description": "Smallholder farmers in Tamar experience 35-40% tomato gluts and rot due to absent micro-cold storage. Distress sales at Rs 2/kg force debt cycles.",
                "expected_outcome": "Passive or evaporative zero-energy cool chamber (ZECC) with solar peltier booster that extends tomato shelf-life by 14 days without high grid power dependence.",
                "district": "Ranchi",
                "latitude": 23.0532,
                "longitude": 85.6425,
                "category": Issue.Category.AGRICULTURE,
                "photo_url": "https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=800",
                "status": Issue.Status.ADOPTED,
                "submitted_by": citizen3,
                "ai_confidence": 0.91,
                "ai_triage_notes": "Triaged: Agricultural post-harvest infrastructure challenge."
            }
        )

        Adoption.objects.get_or_create(
            issue=issue2,
            defaults={
                "university": bau,
                "mode": Adoption.Mode.SELF_ADOPTED
            }
        )

        issue3, _ = Issue.objects.get_or_create(
            title="Interactive Bilingual Mundari-Hindi Digital Reader for Anganwadi Centers",
            defaults={
                "description": "Children entering formal primary schools in Khunti district face acute learning drop-offs due to Hindi language medium when their mother tongue is Mundari.",
                "expected_outcome": "Offline-first audio-visual phonics tool running on low-cost tablets with verified native elder speech synthesis and interactive tribal folk stories.",
                "district": "Khunti",
                "latitude": 23.0722,
                "longitude": 85.2774,
                "category": Issue.Category.EDUCATION,
                "photo_url": "https://images.unsplash.com/photo-1509062522246-3755977927d7?w=800",
                "status": Issue.Status.ASSIGNED,
                "submitted_by": citizen2,
                "ai_confidence": 0.96,
                "ai_triage_notes": "Triaged: Smart Education & Multilingual inclusion."
            }
        )

        Adoption.objects.get_or_create(
            issue=issue3,
            defaults={
                "university": ru,
                "mode": Adoption.Mode.SELF_ADOPTED
            }
        )

        issue4, _ = Issue.objects.get_or_create(
            title="Blast Furnace Slag & Red Mud Runoff Leaching into Subarnarekha Tributaries",
            defaults={
                "description": "Industrial slag storage dumps near Ghatshila leach alkaline heavy metals into irrigation channels during heavy monsoons, damaging paddy yields.",
                "expected_outcome": "Geopolymer binder synthesis converting slag and fly ash into heavy-duty interlocking road pavers with zero toxicity leachate.",
                "district": "East Singhbhum",
                "latitude": 22.5852,
                "longitude": 86.4807,
                "category": Issue.Category.ENVIRONMENT,
                "photo_url": "https://images.unsplash.com/photo-1611273426858-450d8e3c9fce?w=800",
                "status": Issue.Status.ADOPTED,
                "submitted_by": citizen1,
                "ai_confidence": 0.95,
                "ai_triage_notes": "Triaged: Industrial ecology & environmental remediation."
            }
        )

        Adoption.objects.get_or_create(
            issue=issue4,
            defaults={
                "university": nit,
                "mode": Adoption.Mode.SELF_ADOPTED
            }
        )

        issue5, _ = Issue.objects.get_or_create(
            title="Off-Grid Solar-Biomass Hybrid Microgrid for Forest Settlement in Netarhat",
            defaults={
                "description": "PV micro-grids in forest fringe hamlets fail during foggy winter months. Villagers revert to kerosene lamps posing fire risks.",
                "expected_outcome": "Hybrid 5kW biomass gasifier integrated with solar inverter and battery bank for 24/7 hamlet lighting and cold chain support.",
                "district": "Latehar",
                "latitude": 23.4833,
                "longitude": 84.2667,
                "category": Issue.Category.ENERGY,
                "photo_url": "https://images.unsplash.com/photo-1509391365360-2e959784a276?w=800",
                "status": Issue.Status.VALIDATED,
                "submitted_by": citizen2,
                "ai_confidence": 0.89,
                "ai_triage_notes": "Triaged: Rural off-grid renewable energy."
            }
        )

        issue6, _ = Issue.objects.get_or_create(
            title="Ergonomic Handloom Jacquard Assistive Attachment for Tribal Tassar Silk Weavers",
            defaults={
                "description": "Elderly artisans in Seraikela weaving delicate Tassar silk suffer acute musculoskeletal spinal damage from manual treadle lifting.",
                "expected_outcome": "Low-power mechanical counterweight or pneumatically assisted jacquard lifting mechanism deployable on traditional pit looms.",
                "district": "Seraikela Kharsawan",
                "latitude": 22.7000,
                "longitude": 85.9333,
                "category": Issue.Category.RURAL_LIVELIHOODS,
                "photo_url": "https://images.unsplash.com/photo-1607613009820-a29f7bb81c04?w=800",
                "status": Issue.Status.ADOPTED,
                "submitted_by": citizen3,
                "ai_confidence": 0.93,
                "ai_triage_notes": "Triaged: Artisan ergonomics and tribal livelihood preservation."
            }
        )

        Adoption.objects.get_or_create(
            issue=issue6,
            defaults={
                "university": nit,
                "mode": Adoption.Mode.SELF_ADOPTED
            }
        )

        issue7, _ = Issue.objects.get_or_create(
            title="Heavy Monsoon Pothole & Bridge Scour Detection on Rural Haat Corridors",
            defaults={
                "description": "Flash monsoons wash out earthen culverts linking weekly rural haats in Chandankiyari block, stranding vegetable transports.",
                "expected_outcome": "Low-cost ultrasonic water-depth indicator with LoRaWAN wireless beacon warning commercial haulers of submerged bridge causeways.",
                "district": "Bokaro",
                "latitude": 23.6693,
                "longitude": 86.1511,
                "category": Issue.Category.URBAN_INFRA,
                "photo_url": "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?w=800",
                "status": Issue.Status.SUBMITTED,
                "submitted_by": citizen1,
                "ai_confidence": 0.87,
                "ai_triage_notes": "Triaged: Civil infrastructure and transport hazard."
            }
        )

        # 5. Pitches
        # Pitch 1 (Issue 1 - BIT Sindri)
        pitch1, _ = Pitch.objects.get_or_create(
            issue=issue1,
            university=bit,
            title="JalShuddhi: Activated Alumina & Moringa Oleifera Dual-Bed Filter",
            defaults={
                "public_summary": "A natural flocculant stage combined with regenerated activated alumina pellets to strip fluoride to WHO standards, powered by a 150W solar DC pump.",
                "confidential_package": "Stage 1 uses locally roasted moringa seed cake dosage at 50mg/L in a 200L contact vessel. Stage 2 routes filtrate through a 1.2m packed bed of 28-mesh activated alumina at 12 BV/hr hydraulic loading. Adsorption regeneration uses 1% NaOH wash followed by dilute H2SO4 neutralization. PCB schematic uses STM32 MCU for real-time TDS and optical turbidity telemetry.",
                "status": Pitch.Status.SUBMITTED,
                "assigned_mentor": mentor_bit,
            }
        )
        pitch1.student_team.add(student1)

        # Pitch 2 (Issue 1 - BIT Sindri)
        pitch2, _ = Pitch.objects.get_or_create(
            issue=issue1,
            university=bit,
            title="BioSand-Graphene Oxide Nanocomposite Gravity Filter",
            defaults={
                "public_summary": "Gravity-fed multi-tier bio-sand system with an eco-synthesized reduced graphene oxide membrane layer for heavy metal and fluoride sequestration.",
                "confidential_package": "Green synthesis of rGO utilizing Eucalyptus leaf extract at 80C. Dip-coating porous ceramic disks with 0.5 wt% chitosan crosslinked rGO. Flow rate sustained at 18 L/hr under 0.8 bar hydrostatic head.",
                "status": Pitch.Status.SUBMITTED,
            }
        )
        pitch2.student_team.add(student2)

        # Citizen feedback on Pitch 1
        CommunityFeedback.objects.get_or_create(
            pitch=pitch1,
            citizen=citizen1,
            defaults={
                "feedback_text": "The solar pump idea is good because electricity goes out 8 hours a day here. Can the filter media be replaced easily by local youth?",
                "relevance_score": 9,
                "mentor_notes": "Critical operational feedback: team must include a modular cartridge replacement mechanism."
            }
        )

        # Pitch 3 (Issue 2 - BAU)
        pitch3, _ = Pitch.objects.get_or_create(
            issue=issue2,
            university=bau,
            title="Solar-Peltier Zero Energy Cool Chamber (ZECC) for Perishables",
            defaults={
                "public_summary": "Evaporative charcoal-and-brick chamber supplemented by 40W solid-state thermoelectric peltier cooling blocks, maintaining 14C and 85% RH.",
                "confidential_package": "Chamber dimensions 2m x 1m x 1m constructed with porous terracotta cavity bricks. Double wall filled with saturated river sand. Dual 12V 6A Peltier modules driven by 100W solar panel with Arduino PWM controller.",
                "status": Pitch.Status.SELECTED,
                "assigned_mentor": mentor_bau,
            }
        )
        pitch3.student_team.add(student_bau)

        lifecycle3, _ = ProjectLifecycle.objects.get_or_create(
            pitch=pitch3,
            defaults={
                "milestones": [
                    {"id": 1, "title": "Thermal Dissipation & Insulation Prototype", "due_date": "2026-09-25", "completed": True},
                    {"id": 2, "title": "Field Test in Tamar Mandi (7-day tomato trial)", "due_date": "2026-10-15", "completed": True},
                    {"id": 3, "title": "Village Farmer Cooperative Hands-on Training", "due_date": "2026-11-20", "completed": False},
                ],
                "deliverables": "CAD Mechanical Drawings, Peltier Microcontroller Firmware, Tamil/Hindi Farmer Assembly Guide.",
                "outcome_status": ProjectLifecycle.OutcomeStatus.IN_PROGRESS
            }
        )

        # Pitch 4 (Issue 3 - Ranchi University)
        pitch4, _ = Pitch.objects.get_or_create(
            issue=issue3,
            university=ru,
            title="MundariBani: Offline Tribal Speech & Story Tablet App",
            defaults={
                "public_summary": "Android app functioning completely offline with 50 recorded folk stories in bilingual audio and tactile syllable tracing games.",
                "confidential_package": "Architecture: React Native + SQLite offline bundle with Coqui TTS model fine-tuned on 40 hours of phonetically balanced Mundari speech corpus. APK packaged under 45MB.",
                "status": Pitch.Status.SELECTED,
            }
        )
        pitch4.student_team.add(student1)

        lifecycle4, _ = ProjectLifecycle.objects.get_or_create(
            pitch=pitch4,
            defaults={
                "milestones": [
                    {"id": 1, "title": "Field Recordings with Tribal Elders", "due_date": "2026-10-15", "completed": True},
                    {"id": 2, "title": "Phonetic Engine Integration & UX Testing", "due_date": "2026-11-30", "completed": True},
                    {"id": 3, "title": "Pilot in 10 Anganwadis across Khunti", "due_date": "2026-12-20", "completed": False},
                ],
                "deliverables": "v1.2 Signed APK, Mundari Phonetic Dictionary JSON, User Manual in Hindi.",
                "outcome_status": ProjectLifecycle.OutcomeStatus.IN_PROGRESS
            }
        )

        # Pitch 5 (Issue 4 - NIT Jamshedpur)
        pitch5, _ = Pitch.objects.get_or_create(
            issue=issue4,
            university=nit,
            title="Geo-Polymer Slag Road Paver Blocks with Heavy Metal Chelation",
            defaults={
                "public_summary": "Chemical activation of ground granulated blast furnace slag (GGBS) using alkali silicates to manufacture M40 grade paver blocks without Portland cement.",
                "confidential_package": "Optimum mix ratio: 65% GGBS, 25% quarry dust, 10% sodium silicate/NaOH activator at 12M concentration. 28-day compressive strength achieved 44.2 MPa. Toxicity Characteristic Leaching Procedure (TCLP) confirms zero heavy metal migration.",
                "status": Pitch.Status.SELECTED,
                "assigned_mentor": coord_nit,
            }
        )
        pitch5.student_team.add(student_nit)

        lifecycle5, _ = ProjectLifecycle.objects.get_or_create(
            pitch=pitch5,
            defaults={
                "milestones": [
                    {"id": 1, "title": "Compressive Strength & Load Testing", "due_date": "2026-09-10", "completed": True},
                    {"id": 2, "title": "TCLP Leaching Toxicity Compliance Certificate", "due_date": "2026-09-28", "completed": True},
                    {"id": 3, "title": "500-meter Trial Road Paving in Jamshedpur Outskirts", "due_date": "2026-11-15", "completed": False},
                ],
                "deliverables": "NABL Accredited Test Certificate, Concrete Mix Design Standard, Paver Mold Blueprints.",
                "outcome_status": ProjectLifecycle.OutcomeStatus.IN_PROGRESS
            }
        )

        # 6. Industry Engagements (Stabilizing Two-Way Industry-University Connection)
        # Engagement 1: Tata Steel Foundation -> Issue 3 (MundariBani, RU)
        IndustryEngagement.objects.get_or_create(
            issue=issue3,
            pitch=pitch4,
            industry_org=tata,
            defaults={
                "created_by": industry_tata,
                "engagement_type": IndustryEngagement.EngagementType.FUNDING,
                "initiator": IndustryEngagement.Initiator.INDUSTRY,
                "status": IndustryEngagement.Status.ACTIVE,
                "proposal_notes": "Tata Steel Foundation CSR agrees to fund hardware procurement of 100 ruggedized Android tablets for Khunti Anganwadis and sponsor student team stipends.",
                "response_notes": "Ranchi University Review Board accepted proposal with student team onboarding scheduled."
            }
        )

        # Engagement 2: Tata Steel Foundation -> Issue 4 (Slag Pavers, NIT Jamshedpur)
        IndustryEngagement.objects.get_or_create(
            issue=issue4,
            pitch=pitch5,
            industry_org=tata,
            defaults={
                "created_by": industry_tata,
                "engagement_type": IndustryEngagement.EngagementType.PROTOTYPING,
                "initiator": IndustryEngagement.Initiator.INDUSTRY,
                "status": IndustryEngagement.Status.ACTIVE,
                "proposal_notes": "Tata Steel Works provides 50 metric tonnes of granulated blast furnace slag (GGBS) and civil materials laboratory testing support at Jamshedpur plant.",
                "response_notes": "NIT Jamshedpur Materials Testing Lab accepted raw material delivery and testing MOU."
            }
        )

        # Engagement 3: BAU Coordinator -> AgTech MSME (Issue 2 - Tomato ZECC)
        IndustryEngagement.objects.get_or_create(
            issue=issue2,
            pitch=pitch3,
            industry_org=agtech,
            defaults={
                "created_by": mentor_bau,
                "engagement_type": IndustryEngagement.EngagementType.TECHNOLOGY_TRANSFER,
                "initiator": IndustryEngagement.Initiator.UNIVERSITY,
                "status": IndustryEngagement.Status.ACCEPTED,
                "proposal_notes": "Birsa Agricultural University proposes commercialization licensing with Chotanagpur AgTech Innovations to manufacture pre-fabricated modular ZECC cooling kits for Farmer Producer Orgs (FPOs).",
                "response_notes": "Chotanagpur AgTech agreed to manufacture initial run of 25 commercial units under royalty-sharing model."
            }
        )

        # Engagement 4: CIL CSR -> Issue 1 (Topchanchi Water, BIT Sindri)
        IndustryEngagement.objects.get_or_create(
            issue=issue1,
            pitch=pitch1,
            industry_org=cil,
            defaults={
                "created_by": industry_cil,
                "engagement_type": IndustryEngagement.EngagementType.MENTORSHIP,
                "initiator": IndustryEngagement.Initiator.INDUSTRY,
                "status": IndustryEngagement.Status.REQUESTED,
                "proposal_notes": "Central Coalfields Ltd CSR division requests joint advisory and engineering validation to deploy solar-powered water filtration units across 12 mining rehabilitation resettlement colonies in Dhanbad.",
                "response_notes": ""
            }
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded comprehensive real Confluence demo data!"))
