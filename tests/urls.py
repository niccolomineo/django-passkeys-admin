"""URL configuration for the test suite."""

from django.urls import path

from passkeys_admin.sites import PasskeyAdminSite

site = PasskeyAdminSite(name="staff")

urlpatterns = [
    path("admin/", site.urls),
]
