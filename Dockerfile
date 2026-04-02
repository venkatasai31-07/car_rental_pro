# Use your stable Python 3.9-slim base
FROM python:3.9-slim

# Install Nginx and build tools
RUN apt-get update && apt-get install -y \
    nginx \
    build-essential \
    python3-dev \
    gcc \
    g++ \
    cmake \
    make \
    && rm -rf /var/lib/apt/lists/*

# Ensure hnswlib builds without architecture-specific issues
ENV HNSWLIB_NO_NATIVE=1

# Set working directory
WORKDIR /app

# Copy requirement first (to leverage Docker cache)
COPY backend/requirements.txt .
# Use high timeout for unstable internet connections
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# Copy the entire project 
COPY . .

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Configure Nginx to serve static files from /app
RUN sed -i 's|root /usr/share/nginx/html;|root /app;|g' /etc/nginx/conf.d/default.conf

# Create a startup script to support Render/Railway dynamic PORT and large AI models
RUN printf "#!/bin/bash\n\
set -e\n\
# Dynamically replace the port 8080 in nginx config with the \$PORT variable provided at runtime\n\
sed -i \"s/listen 8080;/listen \${PORT:-8080};/g\" /etc/nginx/conf.d/default.conf\n\
\n\
nginx\n\
\n\
# Use 1 worker to keep memory usage under 512MB RAM\n\
# Use 300s timeout to allow the large 368MB AI model to load without being killed\n\
# Consolidated Backend handles both main API and ML API\n\
gunicorn -w 1 --timeout 300 --chdir /app/backend -b 127.0.0.1:5000 app:app\n" > /app/start.sh

RUN chmod +x /app/start.sh

# Expose port 8080 (though Render will override this with its own PORT)
EXPOSE 8080

# Start with our script
CMD ["/app/start.sh"]
