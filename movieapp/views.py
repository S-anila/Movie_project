from django.shortcuts import render, HttpResponseRedirect, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User, Group
from .forms import SignUpForm, AddMovieForm, LoginForm, AddRatingForm
from .models import Movie, Rating
from django.db.models import Sum, Count
from django.contrib import messages
from django.db.models import Q
from django.views.generic import DetailView, UpdateView
from .models import Profile
from .forms import ProfileForm
import pandas as pd
from math import sqrt
import numpy as np
import matplotlib.pyplot as plt
from math import ceil


# Create your views here.

def filterMovieByGenre():
    # filtering by genres
    allMovies = []
    genresMovie = Movie.objects.values('genres', 'id')
    genres = {item["genres"] for item in genresMovie}
    for genre in genres:
        movie = Movie.objects.filter(genres=genre)
        print(movie)
        n = len(movie)
        nSlides = n // 4 + ceil((n / 4) - (n // 4))
        allMovies.append([movie, range(1, nSlides), nSlides])
    params = {'allMovies': allMovies}
    return params


def generateRecommendation(request):
    movie = Movie.objects.all()
    rating = Rating.objects.all()
    x = []
    y = []
    A = []
    B = []
    C = []
    D = []
    # Movie Data Frames
    for item in movie:
        x = [item.id, item.title, item.movieduration, item.image.url, item.genres]
        y += [x]
    movies_df = pd.DataFrame(y, columns=['movieId', 'title', 'movieduration', 'image', 'genres'])
    print("Movies DataFrame")
    print(movies_df)
    print(movies_df.dtypes)
    # Rating Data Frames
    print(rating)
    for item in rating:
        A = [item.user.id, item.movie, item.rating]
        B += [A]
    rating_df = pd.DataFrame(B, columns=['userId', 'movieId', 'rating'])
    print("Rating data Frame")
    rating_df['userId'] = rating_df['userId'].astype(str).astype(np.int64)
    rating_df['movieId'] = rating_df['movieId'].astype(str).astype(np.int64)
    rating_df['rating'] = rating_df['rating'].astype(str).astype(np.float64)
    print(rating_df)
    print(rating_df.dtypes)
    if request.user.is_authenticated:
        userid = request.user.id
        user_ratings = Rating.objects.filter(user=userid).values('movie__title', 'rating')

        if not user_ratings.exists():
            recommenderQuery = None
        else:
            inputMovies = pd.DataFrame.from_records(user_ratings, columns=['title', 'rating'])
            print("Watched Movies by user DataFrame")
            inputMovies['rating'] = inputMovies['rating'].astype(np.float64)
            print(inputMovies.dtypes)

            # Filtering out the movies by title
            inputId = movies_df[movies_df['title'].isin(inputMovies['title'].tolist())]

            # Convert the 'movieId' column to ensure compatibility for merging
            inputId['movieId'] = inputId['movieId'].astype(str)

            # Now merge on the correct columns
            inputMovies = pd.merge(inputId, inputMovies, left_on='movieId', right_on='title')

            # Drop unnecessary columns
            inputMovies = inputMovies.drop(columns=['title'])

            # Final input dataframe
            print(inputMovies)

            # Filtering out users that have watched movies that the input has watched and storing it
            userSubset = rating_df[rating_df['movieId'].isin(inputMovies['movieId'].tolist())]
            print(userSubset.head())

            # Groupby creates several sub dataframes where they all have the same value in the column specified as the parameter
            userSubsetGroup = userSubset.groupby(['userId'])

            # print(userSubsetGroup.get_group(7))

            # Sorting it so users with movie most in common with the input will have priority
            userSubsetGroup = sorted(userSubsetGroup, key=lambda x: len(x[1]), reverse=True)

            print(userSubsetGroup[0:])

            userSubsetGroup = userSubsetGroup[0:]

            # Store the Pearson Correlation in a dictionary, where the key is the user Id and the value is the coefficient
            pearsonCorrelationDict = {}

            # For every user group in our subset
            for name, group in userSubsetGroup:
                # Let's start by sorting the input and current user group so the values aren't mixed up later on
                group = group.sort_values(by='movieId')
                inputMovies = inputMovies.sort_values(by='movieId')
                # Get the N for the formula
                nRatings = len(group)
                # Get the review scores for the movies that they both have in common
                temp_df = inputMovies[inputMovies['movieId'].isin(group['movieId'].tolist())]
                # And then store them in a temporary buffer variable in a list format to facilitate future calculations
                tempRatingList = temp_df['rating'].tolist()
                # Let's also put the current user group reviews in a list format
                tempGroupList = group['rating'].tolist()
                # Now let's calculate the pearson correlation between two users, so called, x and y
                Sxx = sum([i ** 2 for i in tempRatingList]) - pow(sum(tempRatingList), 2) / float(nRatings)
                Syy = sum([i ** 2 for i in tempGroupList]) - pow(sum(tempGroupList), 2) / float(nRatings)
                Sxy = sum(i * j for i, j in zip(tempRatingList, tempGroupList)) - sum(tempRatingList) * sum(
                    tempGroupList) / float(nRatings)

                # If the denominator is different than zero, then divide, else, 0 correlation.
                if Sxx != 0 and Syy != 0:
                    pearsonCorrelationDict[name] = Sxy / sqrt(Sxx * Syy)
                else:
                    pearsonCorrelationDict[name] = 0

            print(pearsonCorrelationDict.items())

            pearsonDF = pd.DataFrame.from_dict(pearsonCorrelationDict, orient='index')
            pearsonDF.columns = ['similarityIndex']
            pearsonDF['userId'] = pearsonDF.index
            pearsonDF.index = range(len(pearsonDF))
            print(pearsonDF.head())

            topUsers = pearsonDF.sort_values(by='similarityIndex', ascending=False)[0:]
            print(topUsers.head())

            topUsersRating = topUsers.merge(rating_df, left_on='userId', right_on='userId', how='inner')
            topUsersRating.head()

            # Multiplies the similarity by the user's ratings
            topUsersRating['weightedRating'] = topUsersRating['similarityIndex'] * topUsersRating['rating']
            topUsersRating.head()

            # Applies a sum to the topUsers after grouping it up by userId
            tempTopUsersRating = topUsersRating.groupby('movieId').sum()[['similarityIndex', 'weightedRating']]
            tempTopUsersRating.columns = ['sum_similarityIndex', 'sum_weightedRating']
            tempTopUsersRating.head()

            # Creates an empty dataframe
            recommendation_df = pd.DataFrame()
            # Now we take the weighted average
            recommendation_df['weighted average recommendation score'] = tempTopUsersRating['sum_weightedRating'] / \
                                                                         tempTopUsersRating['sum_similarityIndex']
            recommendation_df['movieId'] = tempTopUsersRating.index
            recommendation_df.head()

            recommendation_df = recommendation_df.sort_values(by='weighted average recommendation score',
                                                              ascending=False)
            recommender = movies_df.loc[movies_df['movieId'].isin(recommendation_df.head(5)['movieId'].tolist())]
            print(recommender)
            return recommender.to_dict('records')


def home(request):
    params = filterMovieByGenre()
    params['recommended'] = generateRecommendation(request)
    return render(request, 'home.html', params)

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')  # Redirect to the home page after successful signup
    else:
        form = SignUpForm()

    return render(request, 'register.html', {'form': form})


def user_login(request):
    if not request.user.is_authenticated:
        if request.method == 'POST':
            fm = LoginForm(request=request, data=request.POST)
            if fm.is_valid():
                uname = fm.cleaned_data['username']
                upass = fm.cleaned_data['password']
                user = authenticate(username=uname, password=upass)
                if user is not None:
                    login(request, user)
                    messages.success(request, 'Logged in Successfully!!')
                    return HttpResponseRedirect('/dashboard/')
        else:
            fm = LoginForm()
        return render(request, 'login.html', {'form': fm})
    else:
        return HttpResponseRedirect('/dashboard/')


# def addmovie(request):
#     if request.user.is_authenticated:
#         if request.method == 'POST':
#             fm = AddMovieForm(request.POST, request.FILES)
#             if fm.is_valid():
#                 fm.save()
#                 messages.success(request, 'Movie Added Successfully!!!')
#         else:
#             fm = AddMovieForm()
#         return render(request, 'addmovie.html', {'form': fm})
#     else:
#         return HttpResponseRedirect('/login/')

def addmovie(request):
    if request.method == 'POST':
        form = AddMovieForm(request.POST, request.FILES)
        if form.is_valid():
            movie = form.save(commit=False)
            movie.added_by = request.user  # Assuming you have a user field in your Movie model
            movie.save()
            messages.success(request, 'Movie Added Successfully!')
            return redirect('home')  # Redirect to the desired page after adding the movie
    else:
        form = AddMovieForm()

    return render(request, 'addmovie.html', {'form': form})


def update(request, id):
    movie = get_object_or_404(Movie, id=id)
    # Check if the logged-in user is the owner of the movie
    if request.user != movie.added_by:
        return redirect('dashboard')  # Create a permission_denied view or redirect to an appropriate page
    form = AddMovieForm(request.POST or None, request.FILES, instance=movie)
    if form.is_valid():
        form.save()
        return redirect('home')
    return render(request, 'edit_movie.html', {'form': form, 'movie': movie})


def delete(request, id):
    movie = get_object_or_404(Movie, id=id)

    # Check if the logged-in user is the owner of the movie
    if request.user != movie.added_by:
        return redirect('dashboard')  # Create a permission_denied view or redirect to an appropriate page

    if request.method == "POST":
        movie.delete()
        return redirect('home')

    return render(request, 'delete_movie.html', {'movie': movie})


def dashboard(request):
    if request.user.is_authenticated:
        params = filterMovieByGenre()
        params['user'] = request.user
        if request.method == 'POST':
            userid = request.POST.get('userid')
            movieid = request.POST.get('movieId')
            movie = Movie.objects.all()
            u = User.objects.get(pk=userid)
            m = Movie.objects.get(pk=movieid)
            rfm = AddRatingForm(request.POST)
            params['rform'] = rfm
            if rfm.is_valid():
                rat = rfm.cleaned_data['rating']
                count = Rating.objects.filter(user=u, movie=m).count()
                if (count > 0):
                    messages.warning(request, 'You have already submitted your review!!')
                    return render(request, 'dashboard.html', params)
                action = Rating(user=u, movie=m, rating=rat)
                action.save()
                messages.success(request, 'You have submitted' + ' ' + rat + ' ' + "star")
            return render(request, 'dashboard.html', params)
        else:
            # print(request.user.id)
            rfm = AddRatingForm()
            params['rform'] = rfm
            movie = Movie.objects.all()
            return render(request, 'dashboard.html', params)
    else:
        return HttpResponseRedirect('/login/')


def movie_detail(request, movie_id):
    try:
        movie = get_object_or_404(Movie, id=movie_id)
    except Exception as e:
        # Log or handle other exceptions
        raise e

    return render(request, 'movie_details.html', {'movie': movie})


def user_logout(request):
    if request.user.is_authenticated:
        logout(request)
        return HttpResponseRedirect('/login/')




def search_result(request):
    movies = None
    query = None

    if 'q' in request.GET:
        query = request.GET.get('q')
        movies = Movie.objects.filter(Q(genres__icontains=query) | Q(title__icontains=query))

    return render(request, 'search.html', {'query': query, 'movies': movies})


def profile(request):
    user_profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=user_profile)

    return render(request, 'profile.html', {'form': form})


def edit_profile(request):
    profile = Profile.objects.get(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'edit_profile.html', {'form': form})
