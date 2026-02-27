# update script that git pulls, restarts gunicorn server 'zahri' and restarts nginx
git pull origin zahri
uv sync
uv run manage.py collectstatic --noinput
uv run manage.py migrate
sudo systemctl restart zahri
sudo nginx -s reload