import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from scipy.sparse.linalg import svds
import math
from sklearn.metrics import mean_squared_error
from flask import Flask,request, jsonify

# Define the directory containing the CSV files
data_dir = r"C:/Users/HP GEFORCE/Desktop/movie/ml-latest-small"

# Print the current working directory
print(f"Current working directory: {os.getcwd()}")

# Print all files in the data directory
print("Files in data directory:")
for root, dirs, files in os.walk(data_dir):
    for file in files:
        print(os.path.join(root, file))

# Verify if the files exist in the specified directory
required_files = ["ratings.csv", "movies.csv", "tags.csv", "links.csv"]
for file_name in required_files:
    file_path = os.path.join(data_dir, file_name)
    print(f"Checking file: {file_path}")  # Print file path for debugging
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

# Load datasets
ratings = pd.read_csv(os.path.join(data_dir, "ratings.csv"))
movies = pd.read_csv(os.path.join(data_dir, "movies.csv"))
tags = pd.read_csv(os.path.join(data_dir, "tags.csv"))
links = pd.read_csv(os.path.join(data_dir, "links.csv"))



movies.dropna(inplace=True)
ratings.dropna(inplace=True)
tags.dropna(inplace=True)
links.dropna(inplace=True)

ratings.drop_duplicates(inplace=True)
movies.drop_duplicates(inplace=True)
tags.drop_duplicates(inplace=True)
links.drop_duplicates(inplace=True)

# Merge ratings with movie information
ratings_with_movies = pd.merge(ratings, movies, on='movieId')

# Handle missing values
tags['tag'] = tags['tag'].fillna('')

# Display the first few rows of each merged dataset



# Create user-item matrix
user_item_matrix = ratings.pivot(index='userId', columns='movieId', values='rating').fillna(0)

# Calculate user-user similarity
user_similarity = cosine_similarity(user_item_matrix)
user_similarity_df = pd.DataFrame(user_similarity, index=user_item_matrix.index, columns=user_item_matrix.index)



# Create item-user matrix
item_user_matrix = ratings.pivot(index='movieId', columns='userId', values='rating').fillna(0)

# Calculate movie-movie similarity
movie_similarity = cosine_similarity(item_user_matrix)
movie_similarity_df = pd.DataFrame(movie_similarity, index=item_user_matrix.index, columns=item_user_matrix.index)



# Calculate global averages
global_movie_average = ratings.groupby('movieId')['rating'].mean()
global_user_average = ratings.groupby('userId')['rating'].mean()



# Convert user-item matrix to a sparse matrix
user_item_matrix_sparse = user_item_matrix.to_numpy()

# Perform SVD
U, sigma, Vt = svds(user_item_matrix_sparse, k=50)
sigma = np.diag(sigma)

# Predict ratings
predicted_ratings = np.dot(np.dot(U, sigma), Vt)
predicted_ratings_df = pd.DataFrame(predicted_ratings, columns=user_item_matrix.columns, index=user_item_matrix.index)



# Create a movie-tag matrix based on the count of each tag for each movie
movie_tags = tags.groupby(['movieId', 'tag']).size().unstack(fill_value=0)



# Calculate cosine similarity between movies based on tags
content_similarity = cosine_similarity(movie_tags)
content_similarity_df = pd.DataFrame(content_similarity, index=movie_tags.index, columns=movie_tags.index)

# Align matrices for recommendations
aligned_movies = content_similarity_df.index.intersection(predicted_ratings_df.columns)
predicted_ratings_df = predicted_ratings_df[aligned_movies]
content_similarity_df = content_similarity_df.loc[aligned_movies, aligned_movies]

def recommend_movies(user_id, num_recommendations=5):
    # Get the movies already rated by the user
    user_ratings = user_item_matrix.loc[user_id]
    rated_movies = user_ratings[user_ratings > 0].index.tolist()

    # Get predicted ratings for the user (collaborative filtering)
    user_predicted_ratings = predicted_ratings_df.loc[user_id]

    # Align user ratings with aligned_movies
    user_ratings_aligned = user_ratings.reindex(aligned_movies).fillna(0)

    # Combine collaborative filtering and content-based filtering
    recommendations = (user_predicted_ratings + content_similarity_df.dot(user_ratings_aligned)) / 2

    # Exclude movies already rated by the user
    recommendations = recommendations.drop(rated_movies, errors='ignore').sort_values(ascending=False).head(num_recommendations)

    # Get movie titles
    recommended_movie_titles = movies[movies['movieId'].isin(recommendations.index)]['title'].tolist()
    
    return recommended_movie_titles

# Example: Recommend movies for user 1
print(recommend_movies(1))



# Example user-item matrix (actual ratings)
user_item_matrix = pd.DataFrame({
    'movie1': [5, 4, 0, 0, 1],
    'movie2': [0, 2, 3, 0, 4],
    'movie3': [1, 0, 0, 4, 5],
    'movie4': [0, 0, 5, 3, 2],
    'movie5': [4, 0, 2, 0, 0]
}, index=['user1', 'user2', 'user3', 'user4', 'user5'])

# Example predicted ratings (from your recommendation system)
predicted_ratings_df = pd.DataFrame({
    'movie1': [4.8, 3.9, 0.1, 0.3, 1.2],
    'movie2': [0.2, 1.8, 2.9, 0.4, 3.9],
    'movie3': [1.2, 0.5, 0.4, 3.8, 4.9],
    'movie4': [0.3, 0.1, 4.9, 3.2, 2.1],
    'movie5': [3.9, 0.4, 2.1, 0.7, 0.3]
}, index=['user1', 'user2', 'user3', 'user4', 'user5'])

# Ensure alignment of predicted_ratings_df with user_item_matrix
predicted_ratings_df = predicted_ratings_df[user_item_matrix.columns]

# Flatten matrices into 1D arrays
actual_ratings = user_item_matrix.values.flatten()
predicted_ratings = predicted_ratings_df.values.flatten()

# Calculate RMSE
rmse = np.sqrt(mean_squared_error(actual_ratings, predicted_ratings))



# Merge movies with genres
movies_with_genres = movies.copy()
genres = movies_with_genres['genres'].str.get_dummies('|')
movies_with_genres = pd.concat([movies_with_genres, genres], axis=1)

# Create a movie-genre matrix and calculate similarity
movie_genres = movies_with_genres.set_index('movieId')[genres.columns]
genre_similarity = cosine_similarity(movie_genres)
genre_similarity_df = pd.DataFrame(genre_similarity, index=movie_genres.index, columns=movie_genres.index)



# Load datasets (assuming they are already loaded)
# movies, ratings, tags, links

# Create user-item matrix
user_item_matrix = ratings.pivot(index='userId', columns='movieId', values='rating').fillna(0)
user_item_matrix_sparse = user_item_matrix.to_numpy()

import os
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse.linalg import svds
from sklearn.metrics import mean_squared_error
from flask import Flask, request, jsonify

app = Flask(__name__)

# Define the directory containing the CSV files
data_dir = r"C:/Users/HP GEFORCE/Desktop/movie/ml-latest-small"

# Load datasets
ratings = pd.read_csv(os.path.join(data_dir, "ratings.csv"))
movies = pd.read_csv(os.path.join(data_dir, "movies.csv"))
tags = pd.read_csv(os.path.join(data_dir, "tags.csv"))
links = pd.read_csv(os.path.join(data_dir, "links.csv"))

# Preprocess datasets
movies.dropna(inplace=True)
ratings.dropna(inplace=True)
tags.dropna(inplace=True)
links.dropna(inplace=True)

ratings.drop_duplicates(inplace=True)
movies.drop_duplicates(inplace=True)
tags.drop_duplicates(inplace=True)
links.drop_duplicates(inplace=True)

# Merge ratings with movie information
ratings_with_movies = pd.merge(ratings, movies, on='movieId')

# Handle missing values
tags['tag'] = tags['tag'].fillna('')

# Create user-item matrix
user_item_matrix = ratings.pivot(index='userId', columns='movieId', values='rating').fillna(0)

# Calculate user-user similarity
user_similarity = cosine_similarity(user_item_matrix)
user_similarity_df = pd.DataFrame(user_similarity, index=user_item_matrix.index, columns=user_item_matrix.index)

# Create item-user matrix
item_user_matrix = ratings.pivot(index='movieId', columns='userId', values='rating').fillna(0)

# Calculate movie-movie similarity
movie_similarity = cosine_similarity(item_user_matrix)
movie_similarity_df = pd.DataFrame(movie_similarity, index=item_user_matrix.index, columns=item_user_matrix.index)

# Calculate global averages
global_movie_average = ratings.groupby('movieId')['rating'].mean()
global_user_average = ratings.groupby('userId')['rating'].mean()

# Convert user-item matrix to a sparse matrix
user_item_matrix_sparse = user_item_matrix.to_numpy()

# Perform SVD
U, sigma, Vt = svds(user_item_matrix_sparse, k=50)
sigma = np.diag(sigma)

# Predict ratings
predicted_ratings = np.dot(np.dot(U, sigma), Vt)
predicted_ratings_df = pd.DataFrame(predicted_ratings, columns=user_item_matrix.columns, index=user_item_matrix.index)

# Create a movie-tag matrix based on the count of each tag for each movie
movie_tags = tags.groupby(['movieId', 'tag']).size().unstack(fill_value=0)

# Calculate cosine similarity between movies based on tags
content_similarity = cosine_similarity(movie_tags)
content_similarity_df = pd.DataFrame(content_similarity, index=movie_tags.index, columns=movie_tags.index)

# Align matrices for recommendations
aligned_movies = content_similarity_df.index.intersection(predicted_ratings_df.columns)
predicted_ratings_df = predicted_ratings_df[aligned_movies]
content_similarity_df = content_similarity_df.loc[aligned_movies, aligned_movies]

# Merge movies with genres
movies_with_genres = movies.copy()
genres = movies_with_genres['genres'].str.get_dummies('|')
movies_with_genres = pd.concat([movies_with_genres, genres], axis=1)

# Function to recommend movies based on genre
def recommend_movies_by_genre(user_id, genre, num_recommendations=5):
    if genre not in genres.columns:
        return []
    
    # Filter movies by the specified genre
    genre_movies = movies_with_genres[movies_with_genres[genre] == 1]['movieId'].tolist()
    
    # Get the movies already rated by the user
    user_ratings = user_item_matrix.loc[user_id]
    rated_movies = user_ratings[user_ratings > 0].index.tolist()
    
    # Get predicted ratings for the user (collaborative filtering)
    user_predicted_ratings = predicted_ratings_df.loc[user_id]
    
    # Align user ratings with aligned_movies
    user_ratings_aligned = user_ratings.reindex(aligned_movies).fillna(0)
    
    # Combine collaborative filtering and content-based filtering
    recommendations = (user_predicted_ratings + content_similarity_df.dot(user_ratings_aligned)) / 2
    
    # Filter recommendations to only include movies of the specified genre
    recommendations = recommendations[recommendations.index.isin(genre_movies)]
    
    # Exclude movies already rated by the user
    recommendations = recommendations.drop(rated_movies, errors='ignore').sort_values(ascending=False).head(num_recommendations)
    
    # Get movie titles
    recommended_movie_titles = movies[movies['movieId'].isin(recommendations.index)]['title'].tolist()
    
    return recommended_movie_titles

# Define a function to perform SVD and calculate RMSE
def svd_rmse(k):
    U, sigma, Vt = svds(user_item_matrix_sparse, k=k)
    sigma = np.diag(sigma)
    predicted_ratings = np.dot(np.dot(U, sigma), Vt)
    
    # To ensure the shape matches user_item_matrix
    predicted_ratings_df = pd.DataFrame(predicted_ratings, columns=user_item_matrix.columns, index=user_item_matrix.index)
    
    # Only consider non-zero entries in the original user_item_matrix
    non_zero_mask = user_item_matrix.values != 0
    actual_ratings = user_item_matrix.values[non_zero_mask]
    predicted_ratings_non_zero = predicted_ratings_df.values[non_zero_mask]
    
    rmse = np.sqrt(mean_squared_error(actual_ratings, predicted_ratings_non_zero))
    return rmse

# Perform grid search for the best k
latent_factors = [10, 20, 50, 100]
rmse_scores = [svd_rmse(k) for k in latent_factors]
best_k = latent_factors[np.argmin(rmse_scores)]


