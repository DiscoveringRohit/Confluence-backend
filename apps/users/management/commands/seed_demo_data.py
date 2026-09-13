from django.core.management.base import BaseCommand
from apps.users.models import User, University, Organization
from apps.issues.models import Issue, Adoption, StudentNomination
from apps.pitches.models import Pitch, CommunityFeedback, ProjectLifecycle
from apps.engagements.models import IndustryEngagement

class Command(BaseCommand):
    help = "Seed demo universities, organizations, users and societal challenges for Confluence"

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")

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

        # 2. Organizations
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

        # 3. Users
        pwd = "Password@123"

        admin_user, _ = User.objects.get_or_create(
            email="admin@jharkhand.gov.in",
            defaults={"name": "Director HTE (Gov Admin)", "role": User.Role.GOV_ADMIN, "is_staff": True, "is_superuser": True}
        )
        admin_user.set_password(pwd)
        admin_user.save()

        citizen_user, _ = User.objects.get_or_create(
            email="citizen@jharkhand.in",
            defaults={"name": "Rameshwar Munda", "role": User.Role.CITIZEN, "phone": "+91 94311 22334"}
        )
        citizen_user.set_password(pwd)
        citizen_user.save()

        coord_user, _ = User.objects.get_or_create(
            email="coordinator@bitsindri.ac.in",
            defaults={"name": "Prof. S. Soren", "role": User.Role.UNIVERSITY_COORDINATOR, "university": bit, "phone": "+91 94311 55667"}
        )
        coord_user.set_password(pwd)
        coord_user.save()

        mentor_user, _ = User.objects.get_or_create(
            email="mentor@bitsindri.ac.in",
            defaults={"name": "Dr. A. K. Singh (Civil & Env)", "role": User.Role.FACULTY_MENTOR, "university": bit}
        )
        mentor_user.set_password(pwd)
        mentor_user.save()

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

        industry_user, _ = User.objects.get_or_create(
            email="csr@tatasteel.com",
            defaults={"name": "Vikram Sengupta", "role": User.Role.INDUSTRY_PARTNER, "organization": tata}
        )
        industry_user.set_password(pwd)
        industry_user.save()

        # 4. Societal Issues
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
                "submitted_by": citizen_user,
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
                "status": Issue.Status.VALIDATED,
                "submitted_by": citizen_user,
                "ai_confidence": 0.91,
                "ai_triage_notes": "Triaged: Agricultural post-harvest infrastructure challenge."
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
                "submitted_by": citizen_user,
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

        # 5. Pitches for Issue 1 (Dual-Package & Isolation Demo)
        pitch1, _ = Pitch.objects.get_or_create(
            issue=issue1,
            university=bit,
            title="JalShuddhi: Activated Alumina & Moringa Oleifera Dual-Bed Filter",
            defaults={
                "public_summary": "A natural flocculant stage combined with regenerated activated alumina pellets to strip fluoride to WHO standards, powered by a 150W solar DC pump.",
                "confidential_package": "SPECIFICATION & IP PACKAGE: Stage 1 involves locally roasted moringa seed cake dosage at 50mg/L in a 200L contact vessel. Stage 2 routes filtrate through a 1.2m packed bed of 28-mesh activated alumina at 12 BV/hr hydraulic loading. Adsorption regeneration cycle uses 1% NaOH wash followed by dilute H2SO4 neutralization. PCB schematic uses STM32 MCU for real-time TDS and optical turbidity monitoring with GSM telemetry to the district water portal.",
                "status": Pitch.Status.SUBMITTED,
                "assigned_mentor": mentor_user,
            }
        )
        pitch1.student_team.add(student1)

        pitch2, _ = Pitch.objects.get_or_create(
            issue=issue1,
            university=bit,
            title="BioSand-Graphene Oxide Nanocomposite Gravity Filter",
            defaults={
                "public_summary": "Gravity-fed multi-tier bio-sand system with an eco-synthesized reduced graphene oxide membrane layer for heavy metal and fluoride sequestration.",
                "confidential_package": "PROPRIETARY COMPOSITE FORMULATION: Green synthesis of rGO utilizing Eucalyptus leaf extract at 80C. Dip-coating porous ceramic disks with 0.5 wt% chitosan crosslinked rGO. Flow rate sustained at 18 L/hr under 0.8 bar hydrostatic head. Full CAD drawings in SolidWorks 2024 repository commit 4a8b29c.",
                "status": Pitch.Status.SUBMITTED,
            }
        )
        pitch2.student_team.add(student2)

        # Citizen feedback on public summary
        CommunityFeedback.objects.get_or_create(
            pitch=pitch1,
            citizen=citizen_user,
            defaults={
                "feedback_text": "The solar pump idea is good because electricity goes out 8 hours a day here. But can the filter media be replaced easily by local youth?",
                "relevance_score": 9,
                "mentor_notes": "Critical operational feedback: team must include a modular cartridge replacement mechanism."
            }
        )

        # Winning pitch for Issue 3 (Assigned)
        pitch3, _ = Pitch.objects.get_or_create(
            issue=issue3,
            university=ru,
            title="MundariBani: Offline Tribal Speech & Story Tablet App",
            defaults={
                "public_summary": "Android app functioning completely offline with 50 recorded folk stories in bilingual audio and tactile syllable tracing games.",
                "confidential_package": "Architecture: React Native + SQLite offline bundle with Coqui TTS model fine-tuned on 40 hours of phonetically balanced Mundari speech corpus. APK packaged under 45MB.",
                "status": Pitch.Status.SELECTED,
            }
        )
        pitch3.student_team.add(student1)

        lifecycle3, _ = ProjectLifecycle.objects.get_or_create(
            pitch=pitch3,
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

        # Industry partnership for Issue 3
        IndustryEngagement.objects.get_or_create(
            issue=issue3,
            pitch=pitch3,
            industry_org=tata,
            defaults={
                "created_by": industry_user,
                "engagement_type": IndustryEngagement.EngagementType.FUNDING,
                "initiator": IndustryEngagement.Initiator.INDUSTRY,
                "status": IndustryEngagement.Status.ACTIVE,
                "proposal_notes": "Tata Steel Foundation CSR agrees to fund hardware procurement of 100 ruggedized Android tablets for Khunti Anganwadis and sponsor student team stipends."
            }
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded Confluence demo data!"))
