from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, send
import mysql.connector
from dotenv import load_dotenv
import os
#firebase
import firebase_admin
from firebase_admin import auth 
from firebase_admin import credentials
#email provider for sending email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
#import socketio

load_dotenv()

#retrieve email and password from environment variables
SENDER_EMAIL = os.getenv('SENDER_EMAIL') 
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')

import logging

# Set up logging (adjust level as necessary)
logging.basicConfig(level=logging.INFO)


app = Flask(__name__)
CORS(app)
socketio = SocketIO(app)

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
    conn = mysql.connector.connect(
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

    #format result into a list of dictionaries
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

    #return {} eeee
    return jsonify(result)


#API for registering a new user
@app.route('/register', methods=['POST'])
def register():
    #get username, password, and email from the request
    data = request.json
    logging.info(f"Incoming registration data: {data}")
    
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    logging.info(f"Registering user - Username: {username}, Email: {email}, Password Length: {len(password) if password else 'N/A'}")

    if not username or not password or not email:
        return jsonify({"error": "Username, password, and email are required"}), 400

    #firebase email-password authentication 
    try:
        #attempt to create the user in Firebase
        try:
            user = auth.create_user(email=email, password=password, display_name=username)
            uid = user.uid
            logging.info(f"User created in Firebase with UID: {uid}")
        except auth.EmailAlreadyExistsError:
            #if user exists, fetch the user and send verification email
            existing_user = auth.get_user_by_email(email)
            uid = existing_user.uid
            logging.info(f"User with email {email} already exists in Firebase. Sending verification email.")
            try:
                send_verification_email(email)
                logging.info(f"attempting to send verification to {email}")
                #return jsonify({"message": "Verification email resent. Please check your inbox."}), 200
            except Exception as e:
                logging.error("Error sending verification email:", exc_info=True)
                return jsonify({"error": "Failed to send verification email", "details": str(e)}), 503
        except Exception as e:
            logging.error("Error creating user in Firebase:", exc_info=True)
            return jsonify({"error": "Failed to create user in Firebase", "details": str(e)}), 501

    except Exception as e:
        logging.error("Firebase authentication process failed:", exc_info=True)
        return jsonify({"error": "Firebase authentication process failed", "details": str(e)}), 500

    #connect to the database and store the user
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        #insert new user into bookreview_DB
        cursor.execute(
            "INSERT INTO bookreview_DB.users (username, password, email, uid) VALUES (%s, %s, %s, %s)",
            (username, password, email, uid)
        )
        conn.commit()
        logging.info(f"User {username} stored in MySQL database with UID: {uid}")
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        conn.rollback()
        logging.error("Error storing user in MySQL database:", exc_info=True)
        return jsonify({"error": "Failed to store user in MySQL database", "details": str(e)}), 501
    finally:
        cursor.close()
        conn.close()


def send_verification_email(email):
    #generate link for verification
    try:
        verification_link = auth.generate_email_verification_link(email)
        logging.info(f"le email is {email}")
        logging.info(f"Sender email is {SENDER_EMAIL}")
    except Exception as e:
        print(f"Error generating verification link: {e}")
        return

    #email content
    #subject = "Verify Your Email"
    #body = f"Please verify your email by clicking this link: {verification_link}"
    subject = f"{username} VERIFY UR EMAIL PLEASE"
    body = f"CLICK THE LINK NOW: {verification_link}"

    #MIME email message
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Send email using smtplib (this example uses Gmail's SMTP server)
        logging.info("Starting SMTP server connection...")
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            # Start TLS and log the progress
            logging.info("Connected to SMTP server.")
            server.ehlo()
            logging.info("EHLO sent.")
            server.starttls()
            logging.info("TLS session started.")
            server.ehlo()
            logging.info("EHLO sent again after TLS.")
            logging.info(f"Attempting to log in with SENDER_EMAIL: {SENDER_EMAIL}")
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            logging.info("Logged into SMTP server.")
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            logging.info("Email sent.")
            # can add insert values logic here for new users

    except smtplib.SMTPException as e:
        print(f"SMTP error sending email: {e}")
    except Exception as e:
        print(f"General error sending email: {e}")

# @app.route('/register', methods=['POST'])
# def register():
#     # Get username, password, and email from the request
#     data = request.json
#     logging.info(f"Incoming registration data: {data}")

#     username = data.get('username')
#     password = data.get('password')
#     email = data.get('email')

#     logging.info(f"Registering user - Username: {username}, Email: {email}, Password Length: {len(password) if password else 'N/A'}")

#     if not username or not password or not email:
#         return jsonify({"error": "Username, password, and email are required"}), 400

#     # Firebase email-password authentication
#     try:
#         # Attempt to create the user in Firebase
#         try:
#             user = auth.create_user(email=email, password=password, display_name=username)
#             uid = user.uid
#             logging.info(f"User created in Firebase with UID: {uid}")

#             # Generate and send verification email
#             try:
#                 verification_link = auth.generate_email_verification_link(email)
#                 logging.info(f"Verification email sent to {email}")
#                 return jsonify({"message": "User registered successfully. Verification email sent."}), 201
#             except Exception as e:
#                 logging.error("Error sending verification email:", exc_info=True)
#                 return jsonify({"error": "Failed to send verification email", "details": str(e)}), 503

#         except auth.EmailAlreadyExistsError:
#             # If user exists, fetch the user and send verification email again
#             existing_user = auth.get_user_by_email(email)
#             uid = existing_user.uid
#             logging.info(f"User with email {email} already exists in Firebase. Sending verification email.")
#             try:
#                 verification_link = auth.generate_email_verification_link(email)
#                 logging.info(f"Verification email resent to {email}, {verification_link}")
#                 return jsonify({"message": "Verification email resent. Please check your inbox."}), 200
#             except Exception as e:
#                 logging.error("Error sending verification email:", exc_info=True)
#                 return jsonify({"error": "Failed to send verification email", "details": str(e)}), 503

#     except Exception as e:
#         logging.error("Firebase authentication process failed:", exc_info=True)
#         return jsonify({"error": "Firebase authentication process failed", "details": str(e)}), 500

#     # Connect to the database and store the user
#     conn = get_db_connection()
#     cursor = conn.cursor()

#     try:
#         # Insert new user into bookReview_DB
#         cursor.execute(
#             "INSERT INTO bookReview_DB.users (username, password, email, uid) VALUES (%s, %s, %s, %s)",
#             (username, password, email, uid)
#         )
#         conn.commit()
#         logging.info(f"User {username} stored in MySQL database with UID: {uid}")
#         return jsonify({"message": "User registered successfully"}), 201
#     except Exception as e:
#         conn.rollback()
#         logging.error("Error storing user in MySQL database:", exc_info=True)
#         return jsonify({"error": "Failed to store user in MySQL database", "details": str(e)}), 501
#     finally:
#         cursor.close()
#         conn.close()

# Function to log all existing Firebase users
def log_all_firebase_users():
    # Initialize an empty list to hold user info
    users_list = []
    page = auth.list_users()

    # Iterate through each page of users
    while page:
        for user in page.users:
            users_list.append({
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name
            })
        page = page.get_next_page()

    logging.info(f"Existing Firebase users: {users_list}")

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

#live chat route
@app.route('/chat', methods=['POST'])
def create_chat():
    data = request.json
    user_id = data.get("user_id")
    target_user_id = data.get("target_user_id")
    room_name = f"{user_id}_{target_user_id}"
    # Create room and return to frontend
    return jsonify({"room": room_name})

@socketio.on('join')
def handle_join(data):
    join_room(data['room'])
    send(f"{data['username']} has joined the room.", room=data['room'])

@socketio.on('message')
def handle_message(data):
    room = data['room']
    send(data['message'], room=room)

@socketio.on('leave')
def handle_leave(data):
    leave_room(data['room'])
    send(f"{data['username']} has left the room.", room=data['room'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)

