from django.urls import path
from . import views

urlpatterns = [
    # Fils de discussion
    path('messaging/conversations/', views.ConversationListCreateView.as_view(), name='conversation-list-create'),
    path('messaging/conversations/<uuid:conversation_id>/', views.ConversationDetailView.as_view(), name='conversation-detail'),

    path('messaging/conversations/<uuid:conversation_id>/hide/', views.ConversationHideView.as_view(), name='conversation-hide'),

    # Messages dans un fil
    path('messaging/conversations/<uuid:conversation_id>/messages/', views.MessageListCreateView.as_view(), name='message-list-create'),
    path('messaging/conversations/<uuid:conversation_id>/mark-read/', views.MarkReadView.as_view(), name='conversation-mark-read'),

    # Membres de l'équipe (pour le sélecteur de participants)
    path('messaging/team-members/', views.TeamMembersView.as_view(), name='messaging-team-members'),
]
