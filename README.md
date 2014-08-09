Limbo4
======

Limbo4 is bookkeeping software for honor-code stores. These stores are
decentralized marketplaces where anyone may buy or sell items (usually snacks).

The previous version of Limbo was written by derenrich. Its code can be seen
here: [link](https://github.com/derenrich/Limbo3).

Features
--------
 
Current Features:

  * User creation
  * Stocking items
  * Description field for all items
  * Purchasing items
  * Deposit/Withdraw funds
  * Stock search
  * Unstocking goods
  * Stock goods with multiple sellers
  * Optional limbo sales tax
  * Money Transfers
  * Anonymous donations
  * Automated database backup
  * Automatic removal or labelling of expired items
  * Export a user's transactions as csv

Planned Features:

  * Auto-generated statistics
  * Tools to help find discrepancies in bookkeeping / verify integrity of data
  * Email notifications / reminders
  * Debt list ("wall of shame")

Installation
------------

Modify `path_to_limbo` in `server.py` with the absolute path to the limbo4
directory. For example, this might be `/var/www/limbo4/`.

Add the following line to httpd.conf:

```
ScriptAlias /cgi-bin/ "/path/to/limbo4/cgi-bin/"
```

For remote backups, edit `backupdb.sh` with host info.

It is strongly recommended to setup cron jobs to run the scripts `backupdb.sh`,
`statistics.py`, and `expiration.py`.
