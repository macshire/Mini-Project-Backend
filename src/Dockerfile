# Use an official Python image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . .

# Install the dependencies
RUN pip install -r requirements.txt

# Expose port 5000 for the Flask app
EXPOSE 7000

# Command to run the application
CMD ["python3", "app.py"]
