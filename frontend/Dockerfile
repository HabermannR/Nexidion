# Start with a lightweight Node.js image
FROM node:24

# 1. Set the working directory FIRST
WORKDIR /workspace/frontend

# 2. Copy package files
COPY packages/remark-internal-links /workspace/packages/remark-internal-links
COPY frontend/package.json frontend/package-lock.json ./

# 3. Install dependencies (this puts them safely in /app/node_modules)
RUN npm ci

# 4. Copy the rest of the code
COPY frontend/ .

# Start the React app!
# (If you use Vite, this is usually "npm run dev". If Create React App, it's "npm start")
CMD ["npm", "run", "dev"]
