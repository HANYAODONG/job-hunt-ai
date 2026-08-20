FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Use npmmirror for China mainland network
RUN npm config set registry https://registry.npmmirror.com

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
