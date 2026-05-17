FROM python:3.13-slim

# Set WORKDIR to a generic project root inside the container
WORKDIR /app

# Fix the security warning from Docker Scout
RUN pip install --upgrade pip setuptools wheel

# Install uv
RUN pip install uv

# Because the build context will now be the project root,
# we reference the file as backend/requirements.txt
COPY backend/requirements.txt .

# Install dependencies using uv extremely fast
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the entire backend directory AS A PACKAGE
COPY backend/ ./backend/

# Copy the run scripts from the project root
COPY run.py task_runner.py ./

# Run the app via gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "run:app"]