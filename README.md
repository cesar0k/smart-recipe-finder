# Smart Recipe Finder API

This is the backend service for the "Smart Recipe Finder" application, built as part of a technical assessment. It provides a RESTful API for managing and searching recipes, all running within a Docker environment.

## Tech Stack

- **Language:** Python 3.11
- **Framework:** FastAPI
- **Database:** MySQL 8.0
- **ORM:** SQLAlchemy
- **Data Validation:** Pydantic v2
- **Containerization:** Docker & Docker Compose

## Prerequisites

Before you begin, ensure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed on your system.

## Getting Started

Follow these steps to get the application running locally.

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd smart-recipe-finder
```

### 2. Set Up Environment Variables

Create a local environment file by copying the provided example.

```bash
cp .env.example .env
```

The default values are pre-configured for a smooth startup. If you need to change the application or database ports because they are already in use on your machine, you can do so by editing the APP_PORT and MYSQL_PORT variables in your local .env file.


### 3. Build and Run the Application

Use Docker Compose to build the images and start the services in detached mode (`-d`).

```bash
docker-compose up --build -d
```

The API service will now be running and accessible at `http://localhost:8000`.

## API Documentation

Once the application is running, the interactive API documentation (powered by Swagger UI) is available at:

[**http://localhost:8000/docs**](http://localhost:8000/docs)

You can use this interface to explore, test, and interact with all the available API endpoints.

## Project Status

Currently implemented features:
- [x] Project setup with Docker and a scalable layered architecture.
- [x] **Create** and **Read** (by ID and list all) operations for recipes.
- [ ] Update and Delete operations for recipes.
- [ ] Advanced filtering and natural language search.