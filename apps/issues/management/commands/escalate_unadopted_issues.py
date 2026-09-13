from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.issues.models import Issue

class Command(BaseCommand):
    help = "Auto-escalate validated societal issues that remain unadopted past a set window (default: 30 days)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help="Days threshold before an unadopted issue is escalated (default: 30)"
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)

        unadopted_qs = Issue.objects.filter(
            status=Issue.Status.VALIDATED,
            adoption__isnull=True,
            is_escalated=False,
            created_at__lte=cutoff
        )

        count = unadopted_qs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No unadopted issues require escalation at this time."))
            return

        unadopted_qs.update(is_escalated=True)
        self.stdout.write(self.style.WARNING(f"Successfully auto-escalated {count} unadopted challenge(s) older than {days} days."))
