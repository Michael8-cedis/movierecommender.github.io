<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Movie Recommendations</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #000;
            color: #fff;
        }
        h1 {
            text-align: center;
            margin-top: 20px;
        }
        .search-bar-container, .filters-container {
            display: flex;
            justify-content: center;
            margin: 20px 0;
        }
        .search-bar-container input[type="text"], .filters-container select {
            padding: 10px;
            border: none;
            border-radius: 5px;
            width: 100%;
            max-width: 300px;
            margin-right: 10px;
        }
        .search-bar-container input[type="submit"], .filters-container input[type="submit"] {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            background-color: #2196F3;
            color: white;
            cursor: pointer;
        }
        .search-bar-container input[type="submit"]:hover, .filters-container input[type="submit"]:hover {
            background-color: #0b79d0;
        }
        .card-container {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 20px;
            padding: 20px;
        }
        .card {
            background-color: rgba(255, 255, 255, 0.05);
            color: #fff;
            border-radius: 8px;
            overflow: hidden;
            width: 300px;
            box-shadow: 0 4px 8px rgba(255, 255, 255, 0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .card:hover {
            transform: scale(1.09);
            box-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
        }
        .card img {
            width: 100%;
            height: auto;
        }
        .card h2 {
            font-size: 1.2em;
            margin: 10px;
        }
        .card p {
            margin: 0 10px 10px;
        }
        .trailer-btn, .movie-link {
            display: block;
            width: 100%;
            padding: 10px;
            border: none;
            border-radius: 5px;
            text-align: center;
            cursor: pointer;
            text-decoration: none;
        }
        .trailer-btn {
            background-color: #f44336;
            color: white;
        }
        .trailer-btn:hover {
            background-color: #c62828;
        }
        .movie-link {
            background-color: #2196F3;
            color: white;
        }
        .movie-link:hover {
            background-color: #0b79d0;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgba(0, 0, 0, 0.8);
            padding-top: 60px;
        }
        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 20px;
            border: 1px solid #888;
            width: 80%;
        }
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
        }
        .close:hover,
        .close:focus {
            color: black;
            text-decoration: none;
            cursor: pointer;
        }
        iframe {
            width: 100%;
            height: 315px;
        }
    </style>
</head>
<body>
    <h1>Movie Recommendations</h1>

    <!-- Display the welcome message and user ID -->
    {% if message %}
    <p>{{ message }}</p>
    {% endif %}

    <!-- Filters -->
    <div class="filters-container">
        <form action="{{ url_for('recommend') }}" method="post">
            <select name="sort_by">
                <option value="">Sort by</option>
                <option value="most_watched">Most Watched</option>
                <option value="highest_budget">Highest Budget</option>
                <option value="critics_choice">Critics' Choice</option>
                <option value="highly_rated">Highly Rated</option>
                <option value="popularity">Popularity</option>
            </select>
            <select name="genre_id">
                <option value="">Select Genre</option>
                <option value="28">Action</option>
                <option value="12">Adventure</option>
                <option value="16">Animation</option>
                <option value="35">Comedy</option>
                <option value="80">Crime</option>
                <option value="99">Documentary</option>
                <option value="18">Drama</option>
                <option value="10751">Family</option>
                <option value="14">Fantasy</option>
                <option value="36">History</option>
                <option value="27">Horror</option>
                <option value="10402">Music</option>
                <option value="9648">Mystery</option>
                <option value="10749">Romance</option>
                <option value="878">Science Fiction</option>
                <option value="53">Thriller</option>
                <option value="10770">TV Movie</option>
                <option value="10752">War</option>
                <option value="37">Western</option>
            </select>
            <select name="year">
                <option value="">Select Year</option>
                {% for year in range(1900, 2025) %}
                <option value="{{ year }}">{{ year }}</option>
                {% endfor %}
            </select>
            <input type="hidden" name="user_id" value="{{ user_id }}">
            <input type="submit" value="Apply Filters">
        </form>
    </div>

    <!-- Search bar -->
    <div class="search-bar-container">
        <form action="{{ url_for('search') }}" method="post">
            <input type="text" name="search_query" placeholder="Search for movies..." required>
            <input type="hidden" name="user_id" value="{{ user_id }}">
            <input type="submit" value="Search">
        </form>
    </div>

    <!-- Recommendations cards -->
    <div class="card-container">
        {% if recommendations %}
        {% for movie in recommendations %}
        <div class="card">
            <img src="https://image.tmdb.org/t/p/w500{{ movie.cover_photo }}" alt="{{ movie.title }}">
            <h2>{{ movie.title }}</h2>
            <p>{{ movie.desc }}</p>
            <p>Rating: {{ movie.rating }}</p>
            <p>Release Date: {{ movie.release_date }}</p>
            {% if movie.trailer_url %}
            <button class="trailer-btn" onclick="openModal('{{ movie.trailer_url }}')">Watch Trailer</button>
            {% endif %}
            <a href="https://www.themoviedb.org/movie/{{ movie.id }}" class="movie-link" target="_blank">View Movie</a>
        </div>
        {% endfor %}
        {% endif %}
    </div>

    <!-- New Releases section -->
    <h2>New Releases:</h2>
    <div class="card-container">
        {% if new_releases %}
        {% for movie in new_releases %}
        <div class="card">
            <img src="https://image.tmdb.org/t/p/w500{{ movie.cover_photo }}" alt="{{ movie.title }}">
            <h2>{{ movie.title }}</h2>
            <p>{{ movie.desc }}</p>
            <p>Rating: {{ movie.rating }}</p>
            <p>Release Date: {{ movie.release_date }}</p>
            {% if movie.trailer_url %}
            <button class="trailer-btn" onclick="openModal('{{ movie.trailer_url }}')">Watch Trailer</button>
            {% endif %}
            <a href="https://www.themoviedb.org/movie/{{ movie.id }}" class="movie-link" target="_blank">View Movie</a>
        </div>
        {% endfor %}
        {% endif %}
    </div>

    <!-- Search results section -->
    {% if search_results %}
    <h2>Search Results:</h2>
    <div class="card-container">
        {% for movie in search_results %}
        <div class="card">
            <img src="https://image.tmdb.org/t/p/w500{{ movie.cover_photo }}" alt="{{ movie.title }}">
            <h2>{{ movie.title }}</h2>
            <p>{{ movie.desc }}</p>
            <p>Rating: {{ movie.rating }}</p>
            <p>Release Date: {{ movie.release_date }}</p>
            {% if movie.trailer_url %}
            <button class="trailer-btn" onclick="openModal('{{ movie.trailer_url }}')">Watch Trailer</button>
            {% endif %}
            <a href="https://www.themoviedb.org/movie/{{ movie.id }}" class="movie-link" target="_blank">View Movie</a>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <!-- Modal for Trailer -->
    <div id="trailerModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <iframe id="trailerIframe" src="" frameborder="0" allowfullscreen></iframe>
        </div>
    </div>

    <script>
        function openModal(trailerUrl) {
            document.getElementById('trailerIframe').src = trailerUrl;
            document.getElementById('trailerModal').style.display = "block";
        }

        function closeModal() {
            document.getElementById('trailerModal').style.display = "none";
            document.getElementById('trailerIframe').src = "";
        }

        window.onclick = function(event) {
            var modal = document.getElementById('trailerModal');
            if (event.target == modal) {
                modal.style.display = "none";
                document.getElementById('trailerIframe').src = "";
            }
        }
    </script>
</body>
</html>

