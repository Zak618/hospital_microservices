DOCKER_COMPOSE = docker-compose

build:
	$(DOCKER_COMPOSE) up --build -d

start:
	$(DOCKER_COMPOSE) up -d

stop:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f
