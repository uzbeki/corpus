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

# Version 2.0
## Features:

### Advanced Auth
Users will be divided into admins/staff/regular users. 
Stronger security:
    - get rid of passwords and use fingerprint(FaceID, TouchID) login?
    - require a valid email on signup.

### Enable file uploads
PDF, Image, Word file upload by staff or admin only? 
Can ordinary users upload files?

### Support for uploading large text content
Staff/admin can register complete book/article contents in text format. 
All text content should be indexed and easily searchable/analyzed upon.

Rich text format necessary? Is plain text enough?

### Amazon kindle like reader
Most browsers already support reading PDF files. 
Word file can be opened in Microsoft Word app. 
Are special web readers for those files needed? 

Why not only create web reader to read text content itself and let the user read the files on his own?

### Specs and cost
Max expected users would reach 10,000
Peak load:around 100~200 concurrent users right after the launch. maybe lasts for a week
Normal load: a few users at a time.

Peak load time specs:
    6 CPU cores
    64 GB RAM
    50GB of storage (corpus, annotations, database indexes)
    20MB/s (160Mbps) network bandwidth: 200 users downloading 1MB/request every 10seconds. 1Gbps connection is enough

    Assuming it lasts for a week,
    $0.768 per hour server (AWS EC2 m5.4xlarge)
    7 days * 24 hours = 168 hours
    cost to run for a week: 168*0.768 = $129.02

Normal load time specs:
    2 CPU cores
    4 GB RAM
    50GB of storage
    5MB/s network bandwidth

    $0.0416 per hour server (AWS EC2 t3.medium)
    Yearly Hours: 365 days - 7 peak days = 358 days × 24 hours = 8592 hours
    Total Cost: 8592 × $0.0416 = $357.43 per year (~$30/month)

    with load-balancing and static IP, domain name it will be around $45 a month ($540 a year on normal load).

