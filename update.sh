# update script that git pulls, restarts gunicorn server 'corpus' and restarts nginx
git pull origin main
. ./venv/bin/activate
pip install --upgrade -r requirements.txt
python3 manage.py collectstatic --noinput
python3 manage.py migrate
sudo systemctl restart corpus
sudo nginx -s reload