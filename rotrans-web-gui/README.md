## Running in Production Mode

Docker setup is required to the application in production mode. In the project directory execute the following command to build the docker image.

### `docker build -t abc-gui .`

Use the following command to run the docker image.

### `docker run -d abc-gui`

**Alternatively**, you can also pull the existing docker image on the docker hub and run it on your machine.

### `docker pull ramu93/abc-gui:latest`

### `docker run -d -p 80:80 ramu93/abc-gui`

## Running in Development Mode

**Note: Latest version of Node.js runtime is required in order to run this application in development mode.**

In the project directory, you can run:

### `npm install`

This command installs all the required dependencies.

### `npm start`

This command starts the application. You can view the application on browser by using the URL: http://localhost:8080/

