from django.contrib import admin
from .models import Movie, Rating, Profile


# Register your models here.
@admin.register(Movie)
class movieAdmin(admin.ModelAdmin):
    list_display=('id','title','genres','year','image','movieduration','description','actors','trailer')

@admin.register(Rating)
class ratingAdmin(admin.ModelAdmin):
    list_display=('user','movie','rating','rated_date')


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'bio', 'profile_picture')
    search_fields = ('user__username', 'user__email')
admin.site.register(Profile, ProfileAdmin)