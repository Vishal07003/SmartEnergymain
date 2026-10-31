from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from apps.rooms.models import Building, Floor, Room
from apps.rooms.serializers import (
    BuildingSerializer,
    FloorSerializer,
    RoomListSerializer,
    RoomDetailSerializer,
)
from apps.rooms.permissions import IsAdminOrReadOnlyStaff
from apps.rooms.filters import RoomFilter, FloorFilter

@extend_schema_view(
    list=extend_schema(summary="List Buildings", description="Get all campus buildings with total floors and room counts."),
    retrieve=extend_schema(summary="Get Building Details", description="Retrieve details of a single campus building."),
    create=extend_schema(summary="Create Building", description="Register a new building (Admin only)."),
    update=extend_schema(summary="Update Building", description="Update building details (Admin only)."),
    destroy=extend_schema(summary="Delete Building", description="Remove a building (Admin only)."),
)
class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.prefetch_related('floors').all()
    serializer_class = BuildingSerializer
    permission_classes = [IsAdminOrReadOnlyStaff]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['code', 'name', 'total_floors', 'created_at']
    ordering = ['code']

    @extend_schema(
        summary="List Building Floors",
        description="Returns all floors belonging to the specified building.",
        responses={200: FloorSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='floors')
    def floors(self, request, pk=None):
        building = self.get_object()
        floors = building.floors.all()
        serializer = FloorSerializer(floors, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(summary="List Floors", description="Get all campus floors with building relationships."),
    retrieve=extend_schema(summary="Get Floor Details", description="Retrieve details of a single floor."),
    create=extend_schema(summary="Create Floor", description="Create a new floor within a building (Admin only)."),
    update=extend_schema(summary="Update Floor", description="Update floor details (Admin only)."),
    destroy=extend_schema(summary="Delete Floor", description="Remove a floor (Admin only)."),
)
class FloorViewSet(viewsets.ModelViewSet):
    queryset = Floor.objects.select_related('building').prefetch_related('rooms').all()
    serializer_class = FloorSerializer
    permission_classes = [IsAdminOrReadOnlyStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = FloorFilter
    search_fields = ['name', 'building__name', 'building__code']
    ordering_fields = ['level', 'name', 'building__code']
    ordering = ['building', 'level']

    @extend_schema(
        summary="List Floor Rooms",
        description="Returns all rooms located on the specified floor.",
        responses={200: RoomListSerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='rooms')
    def rooms(self, request, pk=None):
        floor = self.get_object()
        rooms = floor.rooms.select_related('floor__building').all()
        serializer = RoomListSerializer(rooms, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List Rooms",
        description="Search, filter, and paginate through campus rooms with occupancy states and device counts.",
        parameters=[
            OpenApiParameter('building', int, description='Filter by Building ID'),
            OpenApiParameter('building_code', str, description='Filter by Building code (e.g. BLD-B)'),
            OpenApiParameter('floor_level', int, description='Filter by Floor level (1, 2, 3...)'),
            OpenApiParameter('occupancy_state', str, description='Filter by Occupancy: EMPTY, ACTIVE, IDLE_TRANSITION'),
            OpenApiParameter('room_type', str, description='Filter by Room Type: Classroom, Computer Lab, Seminar Hall, Research Lab'),
        ]
    ),
    retrieve=extend_schema(summary="Get Room Details", description="Retrieve complete room details including assigned ESP32 devices and sensors."),
    create=extend_schema(summary="Create Room", description="Add a new room to a floor (Admin only)."),
    update=extend_schema(summary="Update Room", description="Update room metadata or configuration (Admin only)."),
    destroy=extend_schema(summary="Delete Room", description="Remove a room from the system (Admin only)."),
)
class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related('floor__building').prefetch_related('devices', 'sensors').all()
    permission_classes = [IsAdminOrReadOnlyStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = RoomFilter
    search_fields = ['name', 'room_number', 'room_type', 'floor__building__name', 'floor__building__code']
    ordering_fields = ['room_number', 'name', 'occupancy_state', 'ml_confidence_score', 'created_at']
    ordering = ['room_number']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RoomDetailSerializer
        return RoomListSerializer

