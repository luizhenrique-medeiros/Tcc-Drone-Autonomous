FROM node:24-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_GOOGLE_MAPS_BROWSER_API_KEY=
ARG VITE_WS_BASE_URL=
ARG VITE_DEMO_MODE=false

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_GOOGLE_MAPS_BROWSER_API_KEY=$VITE_GOOGLE_MAPS_BROWSER_API_KEY \
    VITE_WS_BASE_URL=$VITE_WS_BASE_URL \
    VITE_DEMO_MODE=$VITE_DEMO_MODE

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
