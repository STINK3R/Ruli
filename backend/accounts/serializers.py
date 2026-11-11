from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from . import kyc
from .models import ClassRequirement, DriverVerification, User, VerificationDocument, VerificationStatus
from .verification import REASON_TEXTS, access_policy

# ФИО проверено по документам — менять его можно только новой заявкой «Рули ID».
NAME_LOCKED = (
    VerificationStatus.PENDING,
    VerificationStatus.NEEDS_FIX,
    VerificationStatus.APPROVED,
    VerificationStatus.EXPIRED,
    VerificationStatus.LICENSE_INVALID,
)
NAME_FIELDS = ("first_name", "last_name", "patronymic")


def validate_phone(value):
    phone = kyc.normalize_phone(value)
    if not kyc.PHONE_RE.match(phone):
        raise serializers.ValidationError("Нужен белорусский мобильный номер: +375 29/33/44/25 и 7 цифр.")
    return phone


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    verification_status_display = serializers.CharField(
        source="get_verification_status_display", read_only=True
    )
    access = serializers.SerializerMethodField()
    phone_verified = serializers.BooleanField(read_only=True)
    name_locked = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "patronymic",
            "full_name",
            "phone_number",
            "phone_verified",
            "name_locked",
            "date_of_birth",
            "driver_license_number",
            "driver_license_issued",
            "driving_since",
            "license_expires_on",
            "verification_status",
            "verification_status_display",
            "is_verified",
            "is_staff",
            "date_joined",
            "access",
        )
        # Данные водителя меняются только через заявку «Рули ID» и одобрение модератора.
        read_only_fields = (
            "id",
            "date_of_birth",
            "driver_license_number",
            "driver_license_issued",
            "driving_since",
            "license_expires_on",
            "verification_status",
            "is_staff",
            "date_joined",
        )

    def get_access(self, obj):
        return access_policy(obj)

    def get_name_locked(self, obj):
        return obj.verification_status in NAME_LOCKED

    def validate_phone_number(self, value):
        return validate_phone(value) if value else value

    def validate(self, attrs):
        user = self.instance
        if user and user.verification_status in NAME_LOCKED:
            changed = [name for name in NAME_FIELDS if name in attrs and attrs[name] != getattr(user, name)]
            if changed:
                raise serializers.ValidationError(
                    {changed[0]: "ФИО подтверждено документами — изменить его можно только новой заявкой Рули ID."}
                )
        return attrs

    def update(self, instance, validated_data):
        # Новый номер снова подтверждается кодом из SMS.
        if "phone_number" in validated_data and validated_data["phone_number"] != instance.phone_number:
            instance.phone_verified_at = None
        return super().update(instance, validated_data)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    ref = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=20)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "password_confirm",
            "ref",
            "first_name",
            "last_name",
            "patronymic",
            "phone_number",
            "date_of_birth",
            "driver_license_number",
            "driver_license_issued",
        )
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
            "phone_number": {"required": True, "allow_null": False},
        }

    def validate_phone_number(self, value):
        return validate_phone(value)

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают."})
        return attrs

    def validate_ref(self, value):
        from rewards.services import user_by_code

        if value and user_by_code(value) is None:
            raise serializers.ValidationError("Такого кода приглашения нет — проверьте его у друга.")
        return value

    def create(self, validated_data):
        from rewards.services import attach_referral

        password = validated_data.pop("password")
        ref = validated_data.pop("ref", "")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if ref:
            attach_referral(user, ref)
        return user


class ClassRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassRequirement
        fields = ("car_class", "min_age", "min_experience_years", "min_completed_rentals", "note")


class VerificationDocumentSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = VerificationDocument
        fields = ("kind", "kind_display", "needs_reshoot", "is_demo", "width", "height", "uploaded_at")


class DriverVerificationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    documents = VerificationDocumentSerializer(many=True, read_only=True)
    rejection_text = serializers.SerializerMethodField()
    user_checks = serializers.SerializerMethodField()
    consent = serializers.BooleanField(write_only=True, required=False)
    biometric_consent = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = DriverVerification
        fields = (
            "id",
            "status",
            "status_display",
            "document_type",
            "full_name_on_document",
            "date_of_birth",
            "license_country",
            "license_number",
            "license_issued_on",
            "license_expires_on",
            "category_b_since",
            "personal_number",
            "liveness_passed_at",
            "documents",
            "rejection_reason",
            "rejection_text",
            "reviewer_comment",
            "user_checks",
            "consent",
            "biometric_consent",
            "consent_given_at",
            "biometric_consent_at",
            "submitted_at",
            "reviewed_at",
        )
        read_only_fields = (
            "liveness_passed_at",
            "status",
            "rejection_reason",
            "reviewer_comment",
            "consent_given_at",
            "biometric_consent_at",
            "submitted_at",
            "reviewed_at",
        )

    def get_rejection_text(self, obj):
        return REASON_TEXTS.get(obj.rejection_reason, "")

    def get_user_checks(self, obj):
        # Внутренние подозрения (дубли фото, число попыток) клиенту не показываем.
        hidden = {"duplicate_image", "many_attempts", "name_mismatch", "demo_documents"}
        return [check for check in obj.auto_checks if check["code"] not in hidden]

    def validate_personal_number(self, value):
        return kyc.normalize_personal_number(value)
