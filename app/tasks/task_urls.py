from django.urls import path
from .views.task_view import tasks, task_detail

urlpatterns = [
    path('', tasks, name='task-list-create'),
    path('<int:task_id>', task_detail, name='task-detail'),
]
