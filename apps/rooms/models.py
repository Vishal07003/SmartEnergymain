from django.db import models

class Building(models.Model):
    name = models.CharField(max_length=128, unique=True, db_index=True)
    code = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    total_floors = models.PositiveIntegerField(default=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'buildings'
        ordering = ['code']

    def __str__(self):
        return f'{self.name} ({self.code})'

class Floor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    level = models.IntegerField(default=1)  # e.g., 1, 2, 3, 4
    name = models.CharField(max_length=64)  # e.g., '1st Floor'

    class Meta:
        db_table = 'floors'
        unique_together = ('building', 'level')
        ordering = ['building', 'level']

    def __str__(self):
        return f'{self.building.code} - {self.name}'

class RoomTypeChoices(models.TextChoices):
    CLASSROOM = 'Classroom', 'Classroom'
    COMPUTER_LAB = 'Computer Lab', 'Computer Lab'
    SEMINAR_HALL = 'Seminar Hall', 'Seminar Hall'
    RESEARCH_LAB = 'Research Lab', 'Research Lab'

class OccupancyStateChoices(models.TextChoices):
    EMPTY = 'EMPTY', 'Empty'
    ACTIVE = 'ACTIVE', 'Active'
    IDLE_TRANSITION = 'IDLE_TRANSITION', 'Idle Transition'

class Room(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=128, db_index=True)
    room_number = models.CharField(max_length=32, db_index=True)
    room_type = models.CharField(max_length=32, choices=RoomTypeChoices.choices, default=RoomTypeChoices.CLASSROOM)
    occupancy_state = models.CharField(
        max_length=32,
        choices=OccupancyStateChoices.choices,
        default=OccupancyStateChoices.EMPTY,
        db_index=True
    )
    ml_confidence_score = models.FloatField(default=0.95)
    idle_timer_minutes = models.PositiveIntegerField(default=0)
    last_state_change = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rooms'
        unique_together = ('floor', 'room_number')
        ordering = ['room_number']

    def __str__(self):
        return f'{self.room_number} - {self.name} ({self.occupancy_state})'

