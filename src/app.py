from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import os

app = Flask(__name__)
CORS(app)

@app.get("/") # Like flask, declares get method and url
def root(): # dBecause we use ASGI, async is added here. If the 3rd party does not support it, then remove async
    host=os.getenv("DB_HOST", "localhost"),  # You can change 'localhost' to the service name 'db' if you're using Docker for MySQL.
    user=os.getenv("DB_USER", "user"),
    password=os.getenv("DB_PASSWORD", "userpassword"),
    database=os.getenv("DB_NAME", "bookreview_DB")
    
    print(host, user, password)
    return {"host": host, "user": user, "password": password, "database": database}
    
# # Database connections
# def get_db_connection():
#     conn = mysql.connector.connect(
#         host=os.getenv("DB_HOST", "localhost"),
#         user=os.getenv("DB_USER", "user"),
#         password=os.getenv("DB_PASSWORD", "userpassword"),
#         database=os.getenv("DB_NAME", "user_database")
#     )
#     return conn

# # Simple route
# @app.route('/')
# def home():
#     conn = get_db_connection()
#     cursor = conn.cursor()

#     # Example: Fetch all users
#     cursor.execute("SELECT * FROM users")
#     result = cursor.fetchall()

#     # Print each user row
#     for row in result:
#         print(row)

#     cursor.close()
#     conn.close()
#     return 'Welcome to the Flask Backend Server!'

# # API for registering a new user
# @app.route('/register', methods=['POST'])
# def register():
#     data = request.json
#     username = data.get('username')
#     password = data.get('password')

#     conn = get_db_connection()
#     cursor = conn.cursor()

#     # Insert new user into MySQL database
#     cursor.execute(
#         "INSERT INTO users (username, password) VALUES (%s, %s)", 
#         (username, password)
#     )
#     conn.commit()

#     cursor.close()
#     conn.close()

#     return jsonify({"message": "User registered successfully"}), 201

# # API for logging in a user
# @app.route('/login', methods=['POST'])
# def login():
#     data = request.json
#     username = data.get('username')
#     password = data.get('password')

#     conn = get_db_connection()
#     cursor = conn.cursor()

#     # Fetch user from the database
#     cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
#     user = cursor.fetchone()

#     cursor.close()
#     conn.close()

#     if user:
#         return jsonify({"message": "Login successful"}), 200
#     else:
#         return jsonify({"message": "Invalid credentials"}), 401
# Database connection function

def get_db_connection():
    conn = mysql.connector.connect(\
    #can change 'localhost' to the service name 'db' if using Docker for MySQL.
        host=os.getenv("DB_HOST", "localhost"),  
        user=os.getenv("DB_USER", "user"),
        password=os.getenv("DB_PASSWORD", "userpassword"),
        database=os.getenv("DB_NAME", "bookreview_DB")
    )

    return conn

#route to display users
@app.route('/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    #obj used to interact with db: cursor **
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    # format result into a list of dictionaries
    result = [
        {"id": user[0], 
        "username": user[1], 
        "password": user[2], 
        "created_at": user[3].strftime('%Y-%m-%d %H:%M:%S'), 
        "profilePic": user[4]}
        for user in users
    ]

    # return {}
    return jsonify(result)

#route to display books
@app.route('/books', methods=['GET'])
def get_books():
    conn = get_db_connection()
    #obj used to interact with db: cursor **
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bookreview_DB.books")
    books = cursor.fetchall()

    cursor.close()
    conn.close()

    # format result into a list of dictionaries
    result = [
        {"objectID": book[0],
        "image": book[1], 
        "title": book[2], 
        "url": book[3], 
        "author": book[4],
        "num_comments": book[5],
        "points": book[6],
        "genre": book[7],
        "ranking": book[8]}
        for book in books
    ]

    # return {} eeee
    return jsonify(result)


#API for registering a new user
@app.route('/register', methods=['POST'])
def register():
    #get username and password from the request
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    #connect to the database **
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        #insert new user into bookReview_DB
        cursor.execute(
            #%s is placeholder for string **
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, password)
        )
        conn.commit()

        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# @app.route('/reviews', methods=['DELETE'])
# def review():
#     #add in deleting review and removing it from DB logic

# @app.route('/users', methods=['PUT'])
# def profilePic():
#     #add in inserting links for profile pictures

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)