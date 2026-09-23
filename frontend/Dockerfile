FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com

COPY . .
RUN npm run build

FROM nginx:alpine

# 官方 entrypoint 的 ipv6 脚本会卡在 `apk manifest nginx`，导致 nginx 永远起不来。
# 我们自己的 nginx.conf 已写死 listen 80，不需要这个脚本。
RUN rm -f /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
