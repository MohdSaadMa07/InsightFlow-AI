from django.db import models as db_models
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from analytics.models import FunnelAnalysis, FunnelDefinition
from events.models import Event
from projects.models import Project
from semantic.models import EventMapping
from semantic.serializers import DetectResultSerializer, EventMappingSerializer


def suggest_category(event_name):
    name = event_name.lower().replace('_', ' ').replace('-', ' ')

    patterns = {
        'authentication': ['login', 'signup', 'register', 'logout', 'auth', 'authenticate', 'verify', 'password', 'reset'],
        'discovery': ['view', 'browse', 'search', 'explore', 'find', 'discover', 'visit', 'land', 'impression', 'category'],
        'engagement': ['click', 'tap', 'scroll', 'share', 'comment', 'like', 'rate', 'review', 'download', 'play', 'watch', 'read', 'submit', 'wishlist', 'favourite', 'favorite', 'filter'],
        'purchase_intent': ['cart', 'bag', 'wishlist', 'favorite', 'save', 'compare', 'add', 'intent', 'buy_now', 'buy'],
        'checkout': ['checkout', 'payment', 'billing', 'shipping', 'address', 'delivery', 'pay'],
        'conversion': ['purchase', 'buy', 'order', 'success', 'complete', 'confirm', 'thank', 'subscribe', 'upgrade', 'paid'],
        'exit': ['exit', 'close', 'tab', 'browser', 'window', 'session_end', 'end', 'leave', 'unload'],
        'support': ['support', 'help', 'contact', 'refund', 'cancel', 'complaint', 'feedback', 'faq', 'ticket'],
    }

    words = name.split()
    best_cat = 'unknown'
    best_score = 0

    for category, keywords in patterns.items():
        score = 0
        for word in words:
            for kw in keywords:
                if word == kw or word.startswith(kw) or kw.startswith(word):
                    score += 1
                elif len(word) > 3 and len(kw) > 3:
                    overlap = len(set(word) & set(kw)) / max(len(set(word) | set(kw)), 1)
                    if overlap > 0.6:
                        score += 0.5
        if score > best_score:
            best_score = score
            best_cat = category

    confidence = min(best_score / max(len(words), 1), 1.0)
    return best_cat, round(confidence, 2)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def detect(request):
    project_id = request.data.get('project_id')
    if not project_id:
        return Response({'error': 'project_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        project = request.user.organization.projects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

    existing = set(EventMapping.objects.filter(project=project).values_list('event_name', flat=True))
    all_events = set(Event.objects.filter(project=project).values_list('event_name', flat=True).distinct())
    new_events = all_events - existing

    results = []
    for event_name in new_events:
        cat, confidence = suggest_category(event_name)
        is_new = confidence < 0.7
        used_in_funnel = cat in EventMapping.FUNNEL_CATEGORIES
        mapping, created = EventMapping.objects.update_or_create(
            project=project,
            event_name=event_name,
            defaults={
                'category': cat if not is_new else 'unknown',
                'used_in_funnel': used_in_funnel if not is_new else False,
                'is_auto_detected': not is_new,
            }
        )
        results.append({
            'event_name': event_name,
            'suggested_category': cat,
            'confidence': confidence,
            'status': 'new' if is_new else 'auto_mapped',
            'used_in_funnel': used_in_funnel if not is_new else False,
        })

    return Response(DetectResultSerializer(results, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_mappings(request):
    project_id = request.GET.get('project_id')
    if not project_id:
        return Response({'error': 'project_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        project = request.user.organization.projects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

    mappings = EventMapping.objects.filter(project=project)
    return Response(EventMappingSerializer(mappings, many=True).data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_mapping(request, mapping_id):
    try:
        mapping = EventMapping.objects.get(id=mapping_id, project__organization=request.user.organization)
    except EventMapping.DoesNotExist:
        return Response({'error': 'Mapping not found'}, status=status.HTTP_404_NOT_FOUND)

    category = request.data.get('category')
    if category:
        mapping.category = category
        mapping.is_auto_detected = False
        if 'used_in_funnel' in request.data:
            mapping.used_in_funnel = request.data['used_in_funnel']
        else:
            mapping.used_in_funnel = category in EventMapping.FUNNEL_CATEGORIES
        mapping.save()

    return Response(EventMappingSerializer(mapping).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def compute_funnel(request):
    project_id = request.data.get('project_id')
    if not project_id:
        return Response({'error': 'project_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        project = request.user.organization.projects.get(id=project_id)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

    days = int(request.data.get('days', 30))
    start_date = timezone.now().date() - timezone.timedelta(days=days)

    funnel_def, _ = FunnelDefinition.objects.get_or_create(
        project=project,
        name='Main Funnel',
        defaults={
            'steps': ['discovery', 'engagement', 'purchase_intent', 'conversion'],
        }
    )

    mappings = EventMapping.objects.filter(project=project)
    if not mappings.exists():
        return Response({'error': 'No event mappings found. Run detection first.'}, status=status.HTTP_400_BAD_REQUEST)

    category_to_events = {}
    for m in mappings:
        if m.used_in_funnel and m.category != 'unknown':
            category_to_events.setdefault(m.category, []).append(m.event_name)

    FunnelAnalysis.objects.filter(project=project, funnel=funnel_def, date__gte=start_date).delete()

    steps = funnel_def.steps
    prev_users = None
    prev_count_val = None
    results = []

    for order, category in enumerate(steps):
        event_names = set(category_to_events.get(category, []))
        has_events = bool(event_names)

        if has_events:
            step_users = set(
                Event.objects.filter(
                    project=project,
                    event_name__in=event_names,
                    timestamp__date__gte=start_date,
                ).exclude(
                    db_models.Q(user_id__isnull=True) | db_models.Q(user_id='')
                ).values_list('user_id', flat=True).distinct()
            )
            if prev_users is not None:
                step_users &= prev_users
        else:
            step_users = prev_users if prev_users is not None else set()

        count = len(step_users)
        if prev_users is not None:
            prev_count_val = len(prev_users)
        else:
            prev_count_val = count

        prev_users = step_users

        conversion_rate = round((count / prev_count_val * 100) if prev_count_val > 0 else 0, 1)

        FunnelAnalysis.objects.create(
            project=project,
            funnel=funnel_def,
            date=timezone.now().date(),
            step_order=order,
            step_name=category,
            count=count,
            conversion_rate=conversion_rate,
        )

        results.append({
            'step_order': order,
            'step_name': category,
            'count': count,
            'conversion_rate': conversion_rate,
        })

    first_count = results[0]['count'] if results else 0
    last_count = results[-1]['count'] if results else 0

    return Response({
        'funnel_id': funnel_def.id,
        'funnel_name': funnel_def.name,
        'steps': results,
        'total_users': first_count,
        'converted_users': last_count,
        'overall_rate': round((last_count / first_count * 100) if first_count > 0 else 0, 1),
    })
