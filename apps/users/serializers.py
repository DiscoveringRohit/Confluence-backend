from rest_framework import serializers
from .models import User, University, Organization

class UniversitySerializer(serializers.ModelSerializer):
    total_adopted = serializers.SerializerMethodField()
    resolution_rate = serializers.SerializerMethodField()

    class Meta:
        model = University
        fields = ['id', 'name', 'code', 'district', 'total_adopted', 'resolution_rate']

    def get_total_adopted(self, obj):
        return obj.adopted_issues.count()

    def get_resolution_rate(self, obj):
        from apps.issues.models import Issue
        adopted = obj.adopted_issues.count()
        if adopted == 0:
            return 100.0
        resolved = Issue.objects.filter(adoption__university=obj, status='resolved').count()
        return round((resolved / adopted) * 100, 1)


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'org_type', 'website']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'name', 'phone', 'role', 'university', 'organization']

    def validate(self, attrs):
        role = attrs.get('role', User.Role.CITIZEN)
        privileged_roles = {
            User.Role.GOV_ADMIN,
            User.Role.UNIVERSITY_COORDINATOR,
            User.Role.FACULTY_MENTOR,
            User.Role.INDUSTRY_PARTNER,
        }
        if role in privileged_roles:
            raise serializers.ValidationError({
                'role': 'Public registration is only permitted for citizens and students. Privileged roles (coordinator, mentor, industry, government) must be provisioned through administrative invitation.'
            })

        if role == User.Role.STUDENT:
            if not attrs.get('university'):
                raise serializers.ValidationError({
                    'university': 'University affiliation is required for student registration.'
                })
            if attrs.get('organization'):
                raise serializers.ValidationError({
                    'organization': 'Organization cannot be set for student accounts.'
                })
        elif role == User.Role.CITIZEN:
            attrs['university'] = None
            attrs['organization'] = None
            attrs['role'] = User.Role.CITIZEN
        else:
            raise serializers.ValidationError({
                'role': f"Invalid role '{role}' for registration."
            })

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    university_details = UniversitySerializer(source='university', read_only=True)
    organization_details = OrganizationSerializer(source='organization', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'phone', 'role',
            'university', 'university_details',
            'organization', 'organization_details'
        ]
        read_only_fields = ['id', 'email', 'role']


class DirectoryUserSerializer(serializers.ModelSerializer):
    """
    Sanitized user representation for directories and peer discovery (M-01).
    Excludes sensitive personal information such as phone numbers.
    """
    university_details = UniversitySerializer(source='university', read_only=True)
    organization_details = OrganizationSerializer(source='organization', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'role',
            'university', 'university_details',
            'organization', 'organization_details'
        ]
        read_only_fields = fields

