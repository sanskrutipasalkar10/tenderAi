FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_API_URL is baked in at build time (browser-visible, not a secret) —
# docker-compose.yml passes it as a build arg so it points at the API's real
# externally-reachable address, not the docker-internal one.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
