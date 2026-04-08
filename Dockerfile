# Use the official lightweight Python 3.12 image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Run the FastAPI application on the standard Cloud Run port (8080)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]