from django.urls import path, include
from .views.project_view import projects, project_detail
from .views.dependency_view import dependencies, dependency_detail

urlpatterns = [
    path('', projects, name='project-list-create'),
    path('<int:project_id>', project_detail, name='project-detail'),
    path('<int:project_id>/tasks/', include('app.tasks.task_urls')),
    path('<int:project_id>/dependencies', dependencies, name='dependency-list-create'),
    path('<int:project_id>/dependencies/<int:dependency_id>', dependency_detail, name='dependency-detail'),
]
