FROM node:22-alpine AS build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm install

COPY frontend ./
RUN npm run build:core \
    && printf "window.CHAPTERGRAPH_CONFIG = { apiBaseUrl: '/api' };\n" > runtime-config.js

FROM nginx:1.27-alpine

COPY deploy/ecs/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend /usr/share/nginx/html

EXPOSE 80

