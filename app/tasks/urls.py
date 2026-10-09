from django.urls import path, include
from .views.project_view import projects, project_detail

urlpatterns = [
    path('', projects, name='project-list-create'),
    path('<int:project_id>', project_detail, name='project-detail'),
    path('<int:project_id>/tasks/', include('app.tasks.task_urls')),
]
