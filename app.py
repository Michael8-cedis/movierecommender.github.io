from flask import Flask, render_template, request, redirect, url_for
import requests
import random

app = Flask(__name__)

TMDB_API_KEY = '050fb40adf2ab2515436f43302930512'

# Mocked database for users
user_db = {}

# Function to get recommendations by genre from TMDB with sorting and filtering
def recommend_by_genre(genre_id, num_recommendations, sort_by="popularity.desc", year=None):
    sort_options = {
        "most_watched": "watch_count.desc",
        "highest_budget": "budget.desc",
        "critics_choice": "vote_average.desc",
        "highly_rated": "vote_average.desc",
        "popularity": "popularity.desc"
    }
    sort_by = sort_options.get(sort_by, "popularity.desc")
    
    url = f'https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_genres={genre_id}&language=en-US&sort_by={sort_by}&page=1'
    if year:
        url += f'&year={year}'
    
    response = requests.get(url)
    if response.status_code == 200:
        items = response.json().get('results', [])[:num_recommendations]
        recommendations = []
        for item in items:
            movie_id = item['id']
            trailer_url = get_movie_trailer(movie_id)
            recommendations.append({
                'id': movie_id,
                'title': item['title'],
                'desc': item['overview'],
                'rating': item['vote_average'],
                'release_date': item.get('release_date', 'N/A'),
                'cover_photo': item['poster_path'],
                'trailer_url': trailer_url
            })
        return recommendations
    else:
        return []

# Function to search for movies by title from TMDB
def search_movies(title):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}'
    response = requests.get(url)
    if response.status_code == 200:
        search_results = []
        for item in response.json().get('results', []):
            movie_id = item['id']
            trailer_url = get_movie_trailer(movie_id)
            search_results.append({
                'id': movie_id,
                'title': item['title'],
                'desc': item['overview'],
                'rating': item['vote_average'],
                'release_date': item.get('release_date', 'N/A'),
                'cover_photo': item['poster_path'],
                'trailer_url': trailer_url
            })
        return search_results
    else:
        return []

# Function to get the movie trailer URL
def get_movie_trailer(movie_id):
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}&language=en-US'
    response = requests.get(url)
    if response.status_code == 200:
        videos = response.json().get('results', [])
        for video in videos:
            if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                return f'https://www.youtube.com/embed/{video["key"]}'
    return None

# Function to get new releases from TMDB
def get_new_releases():
    url = f'https://api.themoviedb.org/3/movie/now_playing?api_key={TMDB_API_KEY}&language=en-US&page=1'
    response = requests.get(url)
    if response.status_code == 200:
        items = response.json().get('results', [])[:10]  # Limit to the first 10 new releases
        new_releases = []
        for item in items:
            movie_id = item['id']
            trailer_url = get_movie_trailer(movie_id)
            new_releases.append({
                'id': movie_id,
                'title': item['title'],
                'desc': item['overview'],
                'rating': item['vote_average'],
                'release_date': item.get('release_date', 'N/A'),
                'cover_photo': item['poster_path'],
                'trailer_url': trailer_url
            })
        return new_releases
    else:
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_userid', methods=['POST'])
def generate_userid():
    name = request.form['name']
    username = request.form['username']
    genre_id = request.form['genre_id']
    num_recommendations = int(request.form['num_recommendations'])
    sort_by = request.form.get('sort_by', 'popularity.desc')
    year = request.form.get('year')

    # Check if the username already exists
    if username in [user['username'] for user in user_db.values()]:
        return render_template('index.html', message="Username already taken, please choose another one.")

    # Generate a unique 5-digit user ID
    while True:
        user_id = random.randint(10000, 99999)
        if user_id not in user_db:
            break

    user_db[user_id] = {
        'name': name,
        'username': username,
        'genre_id': genre_id,
        'num_recommendations': num_recommendations,
        'sort_by': sort_by,
        'year': year
    }

    # Fetch recommendations
    recommendations = recommend_by_genre(genre_id, num_recommendations, sort_by, year)
    new_releases = get_new_releases()

    message = f"Welcome {name}, your ID is {user_id}. This will be used for your next recommendations."

    return render_template('recommendations.html', name=name, user_id=user_id, recommendations=recommendations, new_releases=new_releases, message=message)

@app.route('/recommend', methods=['POST'])
def recommend():
    user_id = request.form.get('user_id')
    genre_id = request.form.get('genre_id')
    num_recommendations = int(request.form.get('num_recommendations', 20))
    sort_by = request.form.get('sort_by', 'popularity.desc')
    year = request.form.get('year')
    search_query = request.form.get('search_query')

    if user_id:
        # Check if the user is new or existing
        user = user_db.get(int(user_id))
        if user:
            recommendations = recommend_by_genre(genre_id, num_recommendations, sort_by, year)
            message = f"Welcome back {user['name']}! Your ID is {user_id}."
        else:
            recommendations = []
            message = "Invalid User ID. Please try again."
    else:
        recommendations = recommend_by_genre(genre_id, num_recommendations, sort_by, year)
        message = None

    # Handle form submissions for new recommendations
    if 'recommend' in request.form:
        # Process the recommendation form
        movie_id = request.form.get('recommend')
        if movie_id:
            # Simulate adding recommendation (e.g., updating database)
            pass
            # Redirect to the recommendations page with updated recommendations
            return redirect(url_for('recommend', user_id=user_id))

    search_results = search_movies(search_query) if search_query else []
    new_releases = get_new_releases()

    return render_template('recommendations.html', recommendations=recommendations, new_releases=new_releases, message=message, user_id=user_id, search_results=search_results)

@app.route('/retrieve_userid', methods=['POST'])
def retrieve_userid():
    username = request.form['username']

    # Find the user by username
    for user_id, user in user_db.items():
        if user['username'] == username:
            return render_template('index.html', message=f"Your User ID is {user_id}")

    return render_template('index.html', message="Username not found.")

@app.route('/existing_user', methods=['POST'])
def existing_user():
    user_id = request.form.get('user_id')
    user = user_db.get(int(user_id))
    if user:
        return redirect(url_for('recommend', user_id=user_id))
    else:
        return render_template('index.html', message="Invalid User ID. Please try again.")

@app.route('/search', methods=['POST'])
def search():
    search_query = request.form['search_query']
    search_results = search_movies(search_query)
    user_id = request.form['user_id']  # Pass user_id to maintain session

    # Get the current user's name from the user_db
    user_name = user_db.get(int(user_id), {}).get('name', '')

    new_releases = get_new_releases()

    return render_template('recommendations.html', search_results=search_results, new_releases=new_releases, user_id=user_id, name=user_name)

if __name__ == '__main__':
    app.run(debug=True)
