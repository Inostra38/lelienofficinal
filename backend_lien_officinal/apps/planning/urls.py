from django.urls import path
from .views import (
    WeekView,
    ShiftListCreateView,
    ShiftDetailView,
    ShiftPublishView,
    PublishWeekView,
    UnpublishWeekView,
    AbsenceListCreateView,
    AbsenceReviewView,
    AbsenceDeleteView,
    DayStatusListCreateView,
    DayStatusDeleteView,
    MonthlyAbsenceSummaryView,
    PlanningSettingsView,
    WeekTemplateListView,
    WeekTemplateDetailView,
    TemplateShiftListCreateView,
    TemplateShiftDetailView,
    TemplateApplyView,
    TemplateBulkReplaceView,
    BulkShiftUpdateView,
    OpeningHoursView,
    OpeningHoursDetailView,
    OpeningHoursVersionCreateView,
    TimeAdjustmentListCreateView,
    TimeAdjustmentDeleteView,
    AnalyticsView,
    PayeAnalyticsView,
    ConstraintsView,
    ConstraintDetailView,
    GenerateTemplateView,
    GenerateTemplatePollView,
    SplitShiftView,
    TransformShiftView,
    EarlyDepartureView,
    OvertimeView,
    RCRView,
)

urlpatterns = [
    # Semaine complète (shifts + statuts + résumé)
    path('planning/week/', WeekView.as_view(), name='planning-week'),

    # Shifts
    path('planning/shifts/', ShiftListCreateView.as_view(), name='shift-list-create'),
    path('planning/shifts/<int:pk>/', ShiftDetailView.as_view(), name='shift-detail'),
    path('planning/shifts/<int:pk>/publish/', ShiftPublishView.as_view(), name='shift-publish'),
    path('planning/shifts/<int:pk>/split/', SplitShiftView.as_view(), name='shift-split'),
    path('planning/shifts/<int:pk>/transform/', TransformShiftView.as_view(), name='shift-transform'),
    path('planning/shifts/<int:pk>/early-departure/', EarlyDepartureView.as_view(), name='shift-early-departure'),
    path('planning/shifts/<int:pk>/overtime/', OvertimeView.as_view(), name='shift-overtime'),
    path('planning/shifts/<int:pk>/rcr/', RCRView.as_view(), name='shift-rcr'),
    path('planning/publish-week/', PublishWeekView.as_view(), name='publish-week'),
    path('planning/unpublish-week/', UnpublishWeekView.as_view(), name='unpublish-week'),

    # Absences
    path('planning/absences/', AbsenceListCreateView.as_view(), name='absence-list-create'),
    path('planning/absences/<int:pk>/', AbsenceDeleteView.as_view(), name='absence-delete'),
    path('planning/absences/<int:pk>/<str:action>/', AbsenceReviewView.as_view(), name='absence-review'),

    # Statuts journaliers
    path('planning/day-status/', DayStatusListCreateView.as_view(), name='day-status'),
    path('planning/day-status/<str:iso_date>/', DayStatusDeleteView.as_view(), name='day-status-delete'),

    # Résumé mensuel absences
    path('planning/absences/monthly-summary/', MonthlyAbsenceSummaryView.as_view(), name='absence-monthly-summary'),

    # Paramètres planning
    path('planning/settings/', PlanningSettingsView.as_view(), name='planning-settings'),

    # Horaires d'ouverture
    path('planning/opening-hours/', OpeningHoursView.as_view(), name='opening-hours-list'),
    path('planning/opening-hours/versions/', OpeningHoursVersionCreateView.as_view(), name='opening-hours-version-create'),
    path('planning/opening-hours/<int:pk>/', OpeningHoursDetailView.as_view(), name='opening-hours-detail'),

    # Templates semaine
    path('planning/templates/', WeekTemplateListView.as_view(), name='template-list'),
    path('planning/templates/<str:letter>/', WeekTemplateDetailView.as_view(), name='template-detail'),
    path('planning/templates/<str:letter>/shifts/', TemplateShiftListCreateView.as_view(), name='template-shift-list'),
    path('planning/templates/<str:letter>/shifts/<int:pk>/', TemplateShiftDetailView.as_view(), name='template-shift-detail'),
    path('planning/templates/<str:letter>/apply/', TemplateApplyView.as_view(), name='template-apply'),
    path('planning/templates/<str:letter>/apply-bulk/', BulkShiftUpdateView.as_view(), name='template-apply-bulk'),
    path('planning/templates/<str:letter>/bulk-replace/', TemplateBulkReplaceView.as_view(), name='template-bulk-replace'),

    # Ajustements horaires
    path('planning/adjustments/', TimeAdjustmentListCreateView.as_view(), name='adjustment-list-create'),
    path('planning/adjustments/<int:pk>/', TimeAdjustmentDeleteView.as_view(), name='adjustment-delete'),

    # Analytics
    path('planning/analytics/paie/', PayeAnalyticsView.as_view(), name='planning-analytics-paye'),
    path('planning/analytics/', AnalyticsView.as_view(), name='planning-analytics'),

    # Contraintes planning (generate BEFORE <int:pk> to avoid conflict)
    path('planning/constraints/', ConstraintsView.as_view(), name='constraints'),
    path('planning/constraints/generate/', GenerateTemplateView.as_view(), name='generate-template'),
    path('planning/constraints/generate/<str:task_id>/', GenerateTemplatePollView.as_view(), name='generate-template-poll'),
    path('planning/constraints/<int:pk>/', ConstraintDetailView.as_view(), name='constraint-detail'),
]
