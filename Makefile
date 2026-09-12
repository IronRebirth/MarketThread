.PHONY: help up down restart ps logs

help:
	@echo "MarketThread development commands:"
	@echo ""
	@echo "  make up       Start development infrastructure"
	@echo "  make down     Stop development infrastructure"
	@echo "  make restart  Restart development infrastructure"
	@echo "  make ps       Show infrastructure status"
	@echo "  make logs     Follow infrastructure logs"
	@echo ""

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down
	docker compose up -d

ps:
	docker compose ps

logs:
	docker compose logs -f