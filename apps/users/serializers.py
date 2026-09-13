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
