from django.contrib import admin
from .models import Course, Module, Lesson, CourseEnrollment, LessonProgress, DigitalResource

admin.site.register(Course)
admin.site.register(Module)
admin.site.register(Lesson)
admin.site.register(CourseEnrollment)
admin.site.register(LessonProgress)
admin.site.register(DigitalResource)
