from django.urls import path
from . import views

urlpatterns = [
    # Fils de discussion
    path('messaging/conversations/', views.ConversationListCreateView.as_view(), name='conversation-list-create'),
    path('messaging/conversations/<uuid:conversation_id>/', views.ConversationDetailView.as_view(), name='conversation-detail'),

    # Messages dans un fil
    path('messaging/conversations/<uuid:conversation_id>/messages/', views.MessageListCreateView.as_view(), name='message-list-create'),
    path('messaging/conversations/<uuid:conversation_id>/mark-read/', views.MarkReadView.as_view(), name='conversation-mark-read'),

    # Pièces jointes
    path('messaging/messages/<uuid:message_id>/attachments/', views.AttachmentUploadView.as_view(), name='attachment-upload'),
    path('messaging/attachments/<uuid:attachment_id>/download/', views.AttachmentDownloadView.as_view(), name='attachment-download'),

    # Membres de l'équipe (pour le sélecteur de participants)
    path('messaging/team-members/', views.TeamMembersView.as_view(), name='messaging-team-members'),
]
