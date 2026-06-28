from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from analytics.models import DailyActiveUser, EventCount, FunnelAnalysis, RetentionCurve
from analytics.serializers import (
    EventCountSerializer,
    FunnelAnalysisSerializer,
    RetentionCurveSerializer,
)
from events.models import Event
from projects.models import Project


def get_project(request):
    project_id = request.GET.get('project_id')
    if project_id:
        try:
            return request.user.organization.projects.get(id=project_id)
        except (Project.DoesNotExist, ValueError):
            return None
    return request.user.organization.projects.first()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()

    dau = DailyActiveUser.objects.filter(
        project=project, date=today
    ).values_list('count', flat=True).first() or 0

    total_events = Event.objects.filter(project=project).count()
    total_users = Event.objects.filter(project=project).values('user_id').distinct().count()

    return Response({
        'dau': dau,
        'total_events': total_events,
        'total_users': total_users,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_trends(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    days = int(request.GET.get('days', 7))
    start_date = timezone.now().date() - timezone.timedelta(days=days)

    counts = EventCount.objects.filter(
        project=project, date__gte=start_date
    ).order_by('date', 'event_name')

    return Response(EventCountSerializer(counts, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def funnels(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    days = int(request.GET.get('days', 30))
    start_date = timezone.now().date() - timezone.timedelta(days=days)

    analyses = FunnelAnalysis.objects.filter(
        project=project, date__gte=start_date
    ).select_related('funnel').order_by('date', 'step_order')

    return Response(FunnelAnalysisSerializer(analyses, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def retention(request):
    project = get_project(request)
    if not project:
        return Response({'error': 'No project found'}, status=status.HTTP_404_NOT_FOUND)

    curves = RetentionCurve.objects.filter(
        project=project
    ).order_by('-cohort_date')[:30]

    return Response(RetentionCurveSerializer(curves, many=True).data)
