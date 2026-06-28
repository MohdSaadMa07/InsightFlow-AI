from django.contrib.auth import login as django_login
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from projects.models import APIKey, Project
from users.models import Organization, User
from users.serializers import LoginSerializer, SignupSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    if User.objects.filter(username=data['username']).exists():
        return Response({'error': 'Username already taken'}, status=status.HTTP_409_CONFLICT)

    org = Organization.objects.create(
        name=data['organization_name'],
        slug=data['organization_name'].lower().replace(' ', '-')
    )

    user = User.objects.create_user(
        username=data['username'],
        email=data['email'],
        password=data['password'],
        organization=org,
        role='admin'
    )

    project = Project.objects.create(
        organization=org,
        name='Default Project'
    )

    api_key = APIKey.objects.create(
        project=project,
        name='Default'
    )

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        },
        'organization': {
            'id': org.id,
            'name': org.name,
            'slug': org.slug,
        },
        'project': {
            'id': project.id,
            'name': project.name,
        },
        'api_key': api_key.key,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

    user = serializer.validated_data['user']
    django_login(request, user)
    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'token': token.key,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        },
        'organization': {
            'id': user.organization.id,
            'name': user.organization.name,
            'slug': user.organization.slug,
        } if user.organization else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'organization': {
            'id': user.organization.id,
            'name': user.organization.name,
            'slug': user.organization.slug,
        } if user.organization else None,
        'role': user.role,
    })
