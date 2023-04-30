# update script that git pulls, restarts gunicorn server 'corpus' and restarts nginx
git pull
sudo systemctl restart corpus
sudo systemctl restart nginx