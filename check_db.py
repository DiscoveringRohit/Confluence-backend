import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.issues.models import Issue
from apps.pitches.models import Pitch, ProjectLifecycle
from apps.users.models import User, University
from django.db.models import Count

print('=== DATABASE COUNTS ===')
print(f'Issues: {Issue.objects.count()}')
print(f'Pitches: {Pitch.objects.count()}')
print(f'Lifecycles: {ProjectLifecycle.objects.count()}')
print(f'Users: {User.objects.count()}')
print(f'Universities: {University.objects.count()}')
print()

print('=== ISSUE STATUSES ===')
for item in Issue.objects.values('status').annotate(c=Count('id')):
    print(f"  {item['status']}: {item['c']}")
print()

print('=== PITCH STATUSES ===')
for item in Pitch.objects.values('status').annotate(c=Count('id')):
    print(f"  {item['status']}: {item['c']}")
print()

print('=== USER ROLES ===')
for item in User.objects.values('role').annotate(c=Count('id')):
    print(f"  {item['role']}: {item['c']}")
print()

print('=== SAMPLE PITCHES ===')
for p in Pitch.objects.select_related('submitted_by', 'issue').all()[:5]:
    print(f"  id={p.id} | status={p.status} | by={p.submitted_by.email} | issue={p.issue_id}")
print()

print('=== SAMPLE ISSUES ===')
for i in Issue.objects.select_related('submitted_by').all()[:5]:
    print(f"  id={i.id} | status={i.status} | by={i.submitted_by.email}")
print()

print('=== LIFECYCLES ===')
for l in ProjectLifecycle.objects.select_related('pitch').all()[:5]:
    print(f"  id={l.id} | pitch={l.pitch_id} | status={l.status}")
print()

# Check if pitches have university field
print('=== PITCH FIELDS ===')
p = Pitch.objects.first()
if p:
    print(f"  Fields: {[f.name for f in p._meta.fields]}")
print()

# Check engagements models
try:
    from apps.engagements.models import PitchEngagement
    print(f'PitchEngagements: {PitchEngagement.objects.count()}')
except:
    pass
try:
    from apps.engagements.models import Engagement
    print(f'Engagements: {Engagement.objects.count()}')
except Exception as e:
    print(f'No Engagement model: {e}')
