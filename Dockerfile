FROM python:3.12-slim

# Utilisateur sans droits : l'appli ne tourne jamais en root.
RUN useradd --system --create-home --shell /usr/sbin/nologin app
WORKDIR /srv/app
COPY --chown=app:app app.py citation_checker.py ./
COPY --chown=app:app examples ./examples

USER app
# Dans le conteneur il faut écouter sur toutes les interfaces ; c'est compose.yaml qui limite l'accès à la machine hôte.
ENV HOST=0.0.0.0 PORT=8765 NO_BROWSER=1 PYTHONUNBUFFERED=1
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/examples', timeout=3)"
CMD ["python", "app.py"]
