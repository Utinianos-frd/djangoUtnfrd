from django.urls import path
from .views.organization_view import (
    organizations,
    organization_detail,
    invite_detail,
    invite_regenerate,
    invite_deactivate,
    join,
)
from .views.membership_view import members, member_detail
from .views.group_view import groups, group_detail
from .views.group_membership_view import group_members, group_member_detail
from .views.workload_view import workload, workload_member_detail

urlpatterns = [
    path('', organizations, name='organizations'),
    path('join', join, name='organizations-join'),
    path('<int:organization_id>', organization_detail, name='organization-detail'),
    path('<int:organization_id>/invite', invite_detail, name='organization-invite'),
    path('<int:organization_id>/invite/regenerate', invite_regenerate, name='organization-invite-regenerate'),
    path('<int:organization_id>/invite/deactivate', invite_deactivate, name='organization-invite-deactivate'),
    path('<int:organization_id>/members', members, name='organization-members'),
    path('<int:organization_id>/members/<int:user_id>', member_detail, name='organization-member-detail'),
    path('<int:organization_id>/groups', groups, name='groups'),
    path('<int:organization_id>/groups/<int:group_id>', group_detail, name='group-detail'),
    path('<int:organization_id>/groups/<int:group_id>/members', group_members, name='group-members'),
    path(
        '<int:organization_id>/groups/<int:group_id>/members/<int:user_id>',
        group_member_detail,
        name='group-member-detail',
    ),
    path('<int:organization_id>/groups/<int:group_id>/workload', workload, name='group-workload'),
    path(
        '<int:organization_id>/groups/<int:group_id>/workload/<int:user_id>',
        workload_member_detail,
        name='group-workload-member-detail',
    ),
]
