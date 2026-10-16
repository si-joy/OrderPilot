from django.urls import path

from . import views


app_name = "businesses"


urlpatterns = [

    path(
        "settings/",
        views.business_settings,
        name="settings",
    ),

    path(
        "team/",
        views.team_members,
        name="team",
    ),

    path(
        "team/add/",
        views.team_member_add,
        name="team_add",
    ),

    path(
        "team/invite/<uuid:token>/accept/",
        views.team_invite_accept,
        name="team_invite_accept",
    ),

    path(
        "team/invite/<int:pk>/cancel/",
        views.team_invite_cancel,
        name="team_invite_cancel",
    ),

    path(
        "team/<int:pk>/role/",
        views.team_member_role_update,
        name="team_role_update",
    ),

    path(
        "team/<int:pk>/deactivate/",
        views.team_member_deactivate,
        name="team_deactivate",
    ),

    path(
        "team/<int:pk>/restore/",
        views.team_member_restore,
        name="team_restore",
    ),
]