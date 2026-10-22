from rest_framework import serializers
from .models import StaffProfile


class StaffCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=254)
    phone = serializers.RegexField(r"^\+?[\d\s\-\(\)]{7,20}$", max_length=20)
    staff_number = serializers.CharField(max_length=50)
    category = serializers.ChoiceField(choices=StaffProfile.Category.choices)
    company_id = serializers.IntegerField(min_value=1)
    department_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )
    faculty_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    rank = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )


class StrictMutationSerializer(serializers.Serializer):
    revision = serializers.RegexField(r"^[0-9a-f]{64}$")
    reason = serializers.CharField(max_length=500, min_length=5)

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {key: "This field cannot be changed here." for key in sorted(unknown)}
            )
        return attrs


class StaffUpdateSerializer(StrictMutationSerializer):
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    phone = serializers.RegexField(
        r"^\+?[\d\s\-\(\)]{7,20}$", max_length=20, required=False
    )
    staff_number = serializers.CharField(max_length=50, required=False)
    category = serializers.ChoiceField(
        choices=StaffProfile.Category.choices, required=False
    )
    department_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )
    faculty_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    rank = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not (set(attrs) - {"revision", "reason"}):
            raise serializers.ValidationError(
                "Provide at least one staff detail to update."
            )
        return attrs


class StaffStatusSerializer(StrictMutationSerializer):
    active = serializers.BooleanField()
    restore_login = serializers.BooleanField(default=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["restore_login"] and not attrs["active"]:
            raise serializers.ValidationError(
                "Login access cannot be restored while archiving."
            )
        return attrs
