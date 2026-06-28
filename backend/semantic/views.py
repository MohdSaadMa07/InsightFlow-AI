from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from events.models import Event
from projects.models import Project
from semantic.models import EventMapping
from semantic.serializers import DetectResultSerializer, EventMappingSerializer


def suggest_category(event_name):
    name = event_name.lower().replace('_', ' ').replace('-', ' ')

    patterns = {
        'discovery': ['view', 'browse', 'search', 'explore', 'find', 'discover', 'visit', 'land', 'impression'],
        'purchase_intent': ['cart', 'bag', 'wishlist', 'favorite', 'save', 'compare', 'add', 'intent'],
        'checkout': ['checkout', 'payment', 'billing', 'shipping', 'address', 'delivery', 'pay'],
        'conversion': ['purchase', 'buy', 'order', 'success', 'complete', 'confirm', 'thank', 'subscribe', 'upgrade', 'paid'],
        'engagement': ['click', 'tap', 'scroll', 'share', 'comment', 'like', 'rate', 'review', 'login', 'signup', 'register', 'logout', 'download', 'play', 'watch', 'read', 'submit'],
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
        mapping, created = EventMapping.objects.update_or_create(
            project=project,
            event_name=event_name,
            defaults={
                'category': cat if not is_new else 'unknown',
                'is_auto_detected': not is_new,
            }
        )
        results.append({
            'event_name': event_name,
            'suggested_category': cat,
            'confidence': confidence,
            'status': 'new' if is_new else 'auto_mapped',
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
        mapping.save()

    return Response(EventMappingSerializer(mapping).data)
