from django.db import models
from django.conf import settings

class Course(models.Model):
    CATEGORY_CHOICES = (
        ('MARRIAGE_PREP', 'Préparation au Mariage & Alliance'),
        ('CELIBACY_FAITH', 'Célibat Consacré & Sanctification'),
        ('COMMUNICATION', 'Communication & Harmonie du Foyer'),
        ('SPIRITUAL_GROWTH', 'Croissance Spirituelle & Prière'),
        ('FINANCES', 'Finances Bibliques & Gestion Familiale'),
    )

    LEVEL_CHOICES = (
        ('ALL_LEVELS', 'Tous niveaux'),
        ('BEGINNER', 'Fondations'),
        ('INTERMEDIATE', 'Approfondissement'),
        ('ADVANCED', 'Préparation Avancée'),
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='MARRIAGE_PREP')
    level = models.CharField(max_length=30, choices=LEVEL_CHOICES, default='ALL_LEVELS')
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role__in': ['FORMATEUR', 'ADMIN']},
        related_name='courses_instructed'
    )
    thumbnail = models.ImageField(upload_to='academy_thumbnails/', null=True, blank=True)
    thumbnail_url = models.URLField(blank=True, null=True, help_text="URL externe ou alternative pour l'image")
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, default=1.5, help_text="Durée totale estimée en heures")
    is_premium = models.BooleanField(default=False)
    certificate_available = models.BooleanField(default=True, help_text="Délivre un certificat à 100% de complétion")
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"

    @property
    def total_lessons(self):
        return Lesson.objects.filter(module__course=self).count()


class Module(models.Model):
    course = models.ForeignKey(Course, related_name='modules', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - Module {self.order}: {self.title}"


class Lesson(models.Model):
    LESSON_TYPES = (
        ('VIDEO', 'Vidéo d\'enseignement'),
        ('AUDIO', 'Podcast / Audio spirituel'),
        ('READING', 'Lecture & Méditation'),
    )

    module = models.ForeignKey(Module, related_name='lessons', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True, help_text="Transcription, versets et notes de cours")
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPES, default='VIDEO')
    video_url = models.URLField(blank=True, null=True, help_text="Lien YouTube, Vimeo ou MP4 hébergé")
    video_file = models.FileField(upload_to='academy_videos/', null=True, blank=True, help_text="Fichier vidéo téléversé directement")
    audio_file = models.FileField(upload_to='academy_audios/', null=True, blank=True, help_text="Fichier audio pour enseignement vocal")
    attachment = models.FileField(upload_to='academy_attachments/', null=True, blank=True, help_text="Support de cours PDF ou livret")
    duration_minutes = models.IntegerField(default=10, help_text="Durée de la leçon en minutes")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.module.course.title} - {self.title}"


class CourseEnrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='enrollments', on_delete=models.CASCADE)
    course = models.ForeignKey(Course, related_name='enrollments', on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'course')

    def __str__(self):
        return f"{self.user.email} - {self.course.title}"

    @property
    def progress_percentage(self):
        total = self.course.total_lessons
        if total == 0:
            return 100 if self.is_completed else 0
        completed = self.lesson_progress.filter(is_completed=True).count()
        return min(100, int((completed / total) * 100))


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(CourseEnrollment, related_name='lesson_progress', on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')

    def __str__(self):
        return f"{self.enrollment.user.email} - {self.lesson.title} ({'Done' if self.is_completed else 'Pending'})"


class DigitalResource(models.Model):
    RESOURCE_TYPES = (
        ('ebook', 'Livre Digital / Livret PDF'),
        ('podcast', 'Podcast Audio'),
        ('guide', 'Guide Pratique de Prière'),
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPES, default='ebook')
    category = models.CharField(max_length=100, default='Vie Spirituelle & Mariage')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='published_resources'
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_free = models.BooleanField(default=True)
    image_url = models.URLField(blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    audio_file = models.FileField(upload_to='academy_podcasts/', null=True, blank=True)
    document_file = models.FileField(upload_to='academy_ebooks/', null=True, blank=True)
    duration_minutes = models.IntegerField(default=0, help_text="Durée si podcast audio")
    download_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_resource_type_display()})"
