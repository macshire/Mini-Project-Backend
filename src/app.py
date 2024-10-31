from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import os
#firebase
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
#email provider for sending email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import logging

# Set up logging (adjust level as necessary)
logging.basicConfig(level=logging.INFO)


app = Flask(__name__)
CORS(app)

#initialize Firebase Admin SDK
cred = credentials.Certificate("config/hybridtechnologies-miniproject-firebase-adminsdk-l99aa-210da4ec8d.json")
firebase_admin.initialize_app(cred)

@app.get("/") # Like flask, declares get method and url
def root(): # dBecause we use ASGI, async is added here. If the 3rd party does not support it, then remove async
    host=os.getenv("DB_HOST", "localhost"),  # You can change 'localhost' to the service name 'db' if you're using Docker for MySQL.
    user=os.getenv("DB_USER", "user"),
    password=os.getenv("DB_PASSWORD", "userpassword"),
    database=os.getenv("DB_NAME", "bookreview_DB")
    
    print(host, user, password)
    return {"host": host, "user": user, "password": password, "database": database}

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

@app.route('/users/<int:id>/profilePic', methods=['PUT'])
def update_profilePic(id):
    data = request.get_json()  # Get the JSON payload from the request
    profilePic = data.get('profilePic')  # Extract profilePic from the payload

    if not profilePic:
        return jsonify({"error": "No profilePicture link provided"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
        "UPDATE users SET profilePic = %s WHERE id = %s", (profilePic, id)
        )

        conn.commit()

        if cursor.rowcount == 0:
                return jsonify({"error": "User not found"}), 404

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        # Close the cursor and the connection
        cursor.close()
        conn.close()

    return jsonify({"message": "Profile picture updated successfully!"}), 200


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
    print(f"Income data: {data}")
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    logging.info(f"Registering user - Username: {username}, Email: {email}, Password Length: {len(password) if password else 'N/A'}")

    if not username or not password or not email:
        return jsonify({"error": "Username and password are required"}), 400

    # Firebase authentication process
    try:
        # Attempt to create the user in Firebase
        try:
            user = firebase_auth.create_user(email=email, password=password, display_name=username)
            logging.info(f"User created in Firebase with UID: {user.uid}")
        except Exception as e:
            logging.error("Error creating user in Firebase:", exc_info=True)
            return jsonify({"error": "Failed to create user in Firebase", "details": str(e)}), 501

        # Attempt to retrieve UID after user creation
        try:
            uid = user.uid
        except AttributeError as e:
            return jsonify({"error": "Failed to retrieve UID for the user", "details": str(e)}), 502

        # Attempt to send verification email
        try:
            send_verification_email(email)
        except Exception as e:
            return jsonify({"error": "Failed to send verification email", "details": str(e)}), 503

    except Exception as e:
        return jsonify({"error": "Firebase authentication process failed", "details": str(e)}), 500

    #connect to the database **
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        #insert new user into bookReview_DB
        cursor.execute(
            #%s is placeholder for string **
            "INSERT INTO users (username, password, email, uid) VALUES (%s, %s, %s, %s)",
            (username, password, email, uid)
        )
        conn.commit()

        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 501
    finally:
        cursor.close()
        conn.close()

def send_verification_email(email):
    #generating a verfication link
    veritifcation_link = firebase_auth.generate_email_verification_link(email)
    #email content
    sender_email = "YOUR_EMAIL@gmail.com"
    sender_password = "YOUR_APP_PASSWORD"
    subject = "Verify Your Email"
    body = f"Please verify your email by clicking this link: {verification_link}"

    #create MIME email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        #send email using smtplib (this example uses Gmail's SMTP server)
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, msg.as_string())
            print(f"Verification email sent to: {email}")
    except Exception as e:
        print(f"Error sending email: {e}")

#API for handling bookmarks, adding
@app.route('/books/archive/<int:id>', methods=['POST'])
def archive_book(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        #retrieve book data from books table based on the objectID (id)
        cursor.execute("SELECT objectID, title, image, url, author, genre, num_comments, points, ranking FROM bookreview_DB.books WHERE objectID = %s", (id,))
        book = cursor.fetchone()

        if book:
            #insert the book into the archived_books table
            cursor.execute("""
                INSERT INTO bookreview_DB.archived_books (objectID, title, image, url, author, genre, num_comments, points, ranking)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, book)
            conn.commit()


        return jsonify({"message": "Book archived successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

#API for handling bookmarks, removing
@app.route('/books/archive/<int:id>', methods=['DELETE'])
def unarchive_book(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        #retrieve book data from archived_books table based on the objectID (id)
        cursor.execute("SELECT objectID, title, image, url, author, genre, num_comments, points, ranking FROM bookreview_DB.archived_books WHERE objectID = %s", (id,))
        book = cursor.fetchone()

        if book:
            #delete the book from the archived_books table based on objectID
            cursor.execute("DELETE FROM bookreview_DB.archived_books WHERE objectID = %s", (id,))
            conn.commit()


        return jsonify({"message": "Book unarchived successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

#route to display archived books
@app.route('/books/archive', methods=['GET'])
def get_archived_books():
    conn = get_db_connection()
    cursor = conn.cursor()

    #selecting from the archived books table
    cursor.execute("SELECT * FROM bookreview_DB.archived_books")

    archived_books = cursor.fetchall()
    cursor.close()
    conn.close()

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
        for book in archived_books
    ]

    return jsonify(result)

# @app.route('/reviews', methods=['DELETE'])
# def review():
#     #add in deleting review and removing it from DB logic

# @app.route('/users', methods=['PUT'])
# def profilePic():
#     #add in inserting links for profile pictures

@app.route('/message', methods=['POST'])
def message_user():
    conn = get_db_connection()
    cursor = conn.cursor()


#////////////////////////////////////////////////////////////////////////////////////////
#route to display reviews
@app.route('/reviews', methods=['GET'])
def get_reviews():
    conn = get_db_connection()
    #obj used to interact with db: cursor **
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bookreview_DB.reviews")
    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    # format result into a list of dictionaries
    result = [
        {"id": review[0], "review": review[1], "stars": review[2], "created_at": review[3].strftime('%Y-%m-%d %H:%M:%S'), "reviewID": review[4], "bookID": review[5]}
        for review in reviews
    ]


    # return {}
    return jsonify(result)

#API for adding a review
@app.route('/comment', methods=['POST'])
def comment():
    data = request.json
    id = data.get('id')
    review = data.get('review')
    stars = data.get('stars')
    bookID = data.get('bookID')

    #connect to the database **
    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            #%s is placeholder for string **
            "INSERT INTO bookreview_DB.reviews (id, review, stars, bookID) VALUES (%s, %s, %s, %s)",
            (id, review, stars, bookID)
        )
        conn.commit()

        return jsonify({"message": "User commented successfully"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/remove/<int:id>', methods=['DELETE'])
def delete_review(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        #delete the book from the archived_books table based on objectID
        cursor.execute("DELETE FROM bookreview_DB.reviews WHERE reviewID = %s", (id,))
        conn.commit()


        return jsonify({"message": "Review deleted successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)

