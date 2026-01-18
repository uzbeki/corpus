# update script that git pulls, restarts gunicorn server 'zahri' and restarts nginx
git pull origin zahri
. ./.venv/bin/activate
pip install --upgrade -r requirements.txt
python3 manage.py collectstatic --noinput
python3 manage.py migrate
sudo systemctl restart zahri
sudo nginx -s reload