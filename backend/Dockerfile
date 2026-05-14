FROM python:3.13-slim

WORKDIR /backend

# Fix the security warning from Docker Scout
RUN pip install --upgrade pip setuptools wheel

# Install uv
RUN pip install uv

# Copy the exact same requirements.txt you just tested
COPY requirements.txt .

# Install dependencies using uv extremely fast
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the rest of your code
COPY . .

# Run the app
CMD ["python", "app.py"]