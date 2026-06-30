from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from projects.models import APIKey, Project
from projects.serializers import APIKeySerializer, ProjectSerializer


def get_organization(user):
    return getattr(user, 'organization', None)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def project_list(request):
    org = get_organization(request.user)
    if not org:
        return Response({'error': 'No organization found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        projects = Project.objects.filter(organization=org).prefetch_related('api_keys')
        return Response(ProjectSerializer(projects, many=True).data)

    serializer = ProjectSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    project = Project.objects.create(
        organization=org,
        name=serializer.validated_data['name']
    )

    APIKey.objects.create(project=project, name='Default')

    return Response(ProjectSerializer(project).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def project_detail(request, project_id):
    org = get_organization(request.user)
    if not org:
        return Response({'error': 'No organization found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(ProjectSerializer(project).data)

    if request.method == 'PUT':
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    project.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_keys(request, project_id):
    org = get_organization(request.user)
    if not org:
        return Response({'error': 'No organization found'}, status=status.HTTP_404_NOT_FOUND)
    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)
    keys = APIKey.objects.filter(project=project).order_by('-is_active', '-created_at')
    return Response(APIKeySerializer(keys, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_key(request, project_id):
    org = get_organization(request.user)
    if not org:
        return Response({'error': 'No organization found'}, status=status.HTTP_404_NOT_FOUND)
    try:
        project = Project.objects.get(id=project_id, organization=org)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)

    APIKey.objects.filter(project=project, is_active=True).update(is_active=False)
    new_key = APIKey.objects.create(project=project, name='Default')
    return Response(APIKeySerializer(new_key).data, status=status.HTTP_201_CREATED)
