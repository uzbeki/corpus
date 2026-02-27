# update script that git pulls, restarts gunicorn server 'corpus' and restarts nginx
git pull origin main
uv sync
uv run manage.py collectstatic --noinput
uv run manage.py migrate
sudo systemctl restart corpus
sudo nginx -s reload