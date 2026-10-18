from django.urls import path
from .views.focus_session_view import focus_sessions, active_focus_session, end_focus_session
from .views.pomodoro_view import pomodoros, pomodoro_detail

urlpatterns = [
    path('', focus_sessions, name='focus-session-create'),
    path('active', active_focus_session, name='focus-session-active'),
    path('<int:session_id>/end', end_focus_session, name='focus-session-end'),
    path('<int:session_id>/pomodoros', pomodoros, name='pomodoro-create'),
    path('<int:session_id>/pomodoros/<int:pomodoro_id>', pomodoro_detail, name='pomodoro-detail'),
]
