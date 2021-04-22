############################################### STAGE 1 ###################################################

FROM node:9.11.1 as build

WORKDIR /usr/src/app

ENV PATH /usr/src/app/node_modules/.bin:$PATH

COPY package.json /usr/src/app/package.json
COPY package-lock.json /usr/src/app/package-lock.json

RUN npm install --silent

RUN npm install react-scripts@3.4.1 -g --silent

COPY . ./

RUN npm run build

# CMD ["npm", "start"]

############################################### STAGE 2 ###################################################

FROM nginx:1.13.12-alpine

COPY --from=build /usr/src/app/build /usr/share/nginx/html

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]