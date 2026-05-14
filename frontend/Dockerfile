# Start with a lightweight Node.js image
FROM node:24

# Set the working directory inside the container
WORKDIR /

# Copy ONLY the package.json and package-lock.json first
COPY package*.json ./

# Install the dependencies inside the container
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Start the React app!
# (If you use Vite, this is usually "npm run dev". If Create React App, it's "npm start")
CMD ["npm", "run", "dev"]