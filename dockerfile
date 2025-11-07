# Use the official lightweight Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Ensure the data directory exists
RUN mkdir -p /app/data

# Expose the port for the web UI
EXPOSE 8741

# Launch the web app and scheduler supervisor
CMD ["python", "entrypoint.py"]
