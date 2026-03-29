.PHONY: help test test-back test-front

help:
	@echo ""
	@echo "  make test          Lancer tous les tests (backend + frontend)"
	@echo "  make test-back     Lancer uniquement les tests Django"
	@echo "  make test-front    Lancer uniquement les tests Angular"
	@echo ""

test: test-back test-front

test-back:
	@echo "\n── Tests backend ──────────────────────────────────────"
	cd backend_lien_officinal && $(MAKE) test

test-front:
	@echo "\n── Tests frontend ─────────────────────────────────────"
	cd frontend-lien-officinal && npx ng test --watch=false --browsers=ChromeHeadless
