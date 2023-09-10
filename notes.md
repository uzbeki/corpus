2 Databases for english and uzbek 
automatic google translate


database includes newspaper information last 30 years, filter by year, search by words included in newspaper articles.


Relational database that stores information about the newspaper and its articles:
Newspaper:
    - name
    - link to the online source
    - published year
    - issue number

Article:
    - title
    - author
    - newspaper name
    - text content max of 505 words, min 495



Balance:
1. Number of words used per year has to be balanced
2. 


search by article text, 
filter results by year






What to include in general statistics for 30 years:
1. list of most used words ordered by frequency, paginate by 10, can be filtered by year, time duration. Word can be clicked to search for more details about the word.


saytga admin - Nozim aka
Login authorization, general user and admin user
account registration has to be approved by admin

Admin:
- can add new newspaper
- can add new article
- account approval/rejection


Steps:
1. [DONE] Database creation
2. [DONE] Search functionality
3. [DONE] Authentication/login
4. [DONE] Admin panel: add new newspaper, add new article, account approval/rejection
5. General statistics
    1. [DONE] Number of newspapers
    2. 20 most frequent words by language
        overall download
        download by year or years
    3. Number of total 
        - unique words
        - words
    4. Years
6. [DONE] Year page (30 year limit):
    Unique words ordered by frequency (descending)
7. Search result page:
    [DONE] go to article page on button click
    [OPTIONAL] search by parts of speech (noun, verb, adjective, adverb, etc.)
    [DONE] filter by year (start year, end year)
8. [DONE] Newspaper page
    list of articles
9. [DONE] Article page
    content



Target audience: academics, linguists, students, journalists, researchers, etc.

Data aggregation: bu June 1.




# sysadmin notes
sudo nano /etc/systemd/system/corpus.socket

sudo nano /etc/systemd/system/corpus.service

sudo systemctl status corpus.socket

sudo systemctl enable corpus.socket