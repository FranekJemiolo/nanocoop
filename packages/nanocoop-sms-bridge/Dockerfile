# NanoCoop SMS Bridge Daemon Container
FROM node:20-slim

WORKDIR /app

# Create non-root user
RUN groupadd -g 1001 nanocoop && useradd -u 1001 -g nanocoop -m nanocoop

COPY package.json tsconfig.json /app/
COPY src/ /app/src/
COPY tests/ /app/tests/

RUN npm install && npm run build

USER nanocoop

ENV CORE_API_URL=http://core:8000

CMD ["node", "dist/index.js"]
