"""Settings tests."""

from django.test import SimpleTestCase, override_settings

from passkeys_admin.conf import setting


class SettingTests(SimpleTestCase):
    """Tests for reading a passkeys admin setting."""

    def test_an_unset_setting_falls_back_to_its_default(self) -> None:
        """Test that a setting the project leaves out falls back to its default."""
        self.assertEqual(setting("ENROLMENT_MAX_AGE"), 900)

    @override_settings(PASSKEYS_ADMIN_ENROLMENT_MAX_AGE=60)
    def test_a_project_setting_wins_over_the_default(self) -> None:
        """Test that a setting the project declares wins over the default."""
        self.assertEqual(setting("ENROLMENT_MAX_AGE"), 60)
