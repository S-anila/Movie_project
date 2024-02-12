from django.db import models
from django.contrib.auth.models import User

class Movie(models.Model):
    title = models.CharField(max_length=70)
    genres = models.CharField(max_length=70)
    year = models.CharField(max_length=70)
    image = models.ImageField(upload_to="movie_image")
    movieduration = models.CharField(max_length=70)
    description = models.CharField(max_length=150)
    actors = models.CharField(max_length=70)
    trailer = models.URLField(blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.pk)

class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=None)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, default=None)
    rating = models.DecimalField(max_digits=3, decimal_places=2)
    rated_date = models.DateTimeField(auto_now_add=True)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True,null=True)

    def __str__(self):
        return self.user.username
