#!/usr/bin/python3
# Backend to Limbo4. This is called as a cgi script.

# CGI scripts must start with this.
print("Content-Type:text/html\n\n")

import cgi, cgitb
cgitb.enable()
import sqlite3 as sql
import datetime
# All prices should be manipulated as Decimal values roudned to two places after
# the decimal point. All fractions should also be Decimal values.
# Use str(decimal_value) to get the representation to put in the database.
import decimal
from decimal import Decimal
decimal.getcontext().prec = 6
from collections import namedtuple

# There's a decent sqlite tutorial here:
# http://zetcode.com/db/sqlitepythontutorial/
sql_database = 'limbo4.db'

def round_price(decimal_price):
    """Take a decimal value and round down to the nearest cent."""
    return decimal_price.quantize(Decimal('.01'), rounding=decimal.ROUND_DOWN)

def price(string):
    return round_price(Decimal(string))

class Table():
    def __init__(self, name, *fields):
        self.name = name
        self.fields = fields
        self.fieldnames = [field.split()[0] for field in fields]
        self.Tuple = namedtuple(self.name, self.fieldnames)
        self.Tuple.__str__ = lambda T: str(tuple(T))
        self.Tuple.__repr__ = lambda T: str(tuple(T))
    def create(self, db_conn):
        db_conn.execute("CREATE TABLE %s(%s)" %
                              (self.name, ', '.join(self.fields)))
    
    def select(self, conn, where, *args):
        query = "SELECT * FROM %s" % self.name
        if where is not None:
            query += " WHERE %s" % where
        return list(self.Tuple(*row) for row in conn.execute(query, args))

    def select_one(self, conn, where, *args):
        query = "SELECT * FROM %s" % self.name
        if where is not None:
            query += " WHERE %s" % where
        for row in conn.execute(query, args):
            return self.Tuple(*row) # returns just the first row
    
    def delete(self, conn, where, *args):
        query = "DELETE FROM %s WHERE %s" % (self.name, where)
        conn.execute(query, args)
    
    def insert(self, conn, *values):
        query = "INSERT INTO %s VALUES(%s)" % (self.name,
                                               ', '.join('?' * len(values)))
        conn.execute(query, values)
        
    def update(self, conn, field, where, *args):
        query = "UPDATE %s SET %s WHERE %s" % (self.name, field, where)
        conn.execute(query, args)

# Some notes on data storage:
# Balance/Price are python decimal amounts, so they are stored as their
# text representation.
# All dates are stored in ISO 8601 format, which are the default string
# representation of datetime objects.
Users = Table("Users", "Name      TEXT PRIMARY KEY NOT NULL",
                       "Email     TEXT NOT NULL",
                       "Balance   TEXT NOT NULL",
                       "CaltechID INTEGER NOT NULL",
                       "JoinDate  TEXT NOT NULL")

Items = Table("Items", "Name         TEXT PRIMARY KEY NOT NULL",
                       "Count        INTEGER NOT NULL",
                       "Price        TEXT NOT NULL",
                       "Tax          TEXT NOT NULL",
                       "StockDate    TEXT NOT NULL",
                       "ExpiryDate   TEXT NOT NULL",
                       "Description  TEXT")

# An item is allowed multiple sellers. We keep this in a separate table.
# The "profit split" should be a percentage of the price, and should
# always sum up to 100% or less (in the case of optional limbo tax).
Sellers = Table("Sellers", "ItemName     TEXT NOT NULL",
                           "Seller       TEXT NOT NULL",
                           "ProfitSplit  TEXT NOT NULL")

# Transactions
# each field 'ProfitSplit' is some number between 0.0 and 1.0 inclusive.
# likewise with tax, it is some number between 0.0 and 1.0 inclusive.
#   Buying and Selling
#     If a purchase has multiple sellers, then we use multiple rows.
Purchases = Table("Purchases", "ItemName     TEXT NOT NULL",
                               "Date         TEXT NOT NULL",
                               "StockDate    TEXT NOT NULL",
                               "ExpiryDate   TEXT NOT NULL",
                               "Buyer        TEXT NOT NULL",
                               "Seller       TEXT NOT NULL",
                               "ProfitSplit  TEXT NOT NULL",
                               "PriceEach    TEXT NOT NULL",
                               "Count        INTEGER NOT NULL",
                               "Tax          TEXT NOT NULL")

Transfers = Table("Transfers", "Date       TEXT NOT NULL",
                               "Sender     TEXT NOT NULL",
                               "Receiver   TEXT NOT NULL",
                               "Amount     TEXT NOT NULL")

BalanceChanges = Table("BalanceChanges", "Date       TEXT NOT NULL",
                                         "User       TEXT NOT NULL",
                                         "Amount     TEXT NOT NULL")

#   Stocking and Unstocking transactions
#     If a stocked item has multiple sellers, then we use multiple rows.
Stocking = Table("Stocking", "ItemName     TEXT NOT NULL",
                             "Date         TEXT NOT NULL",
                             "StockDate    TEXT NOT NULL",
                             "ExpiryDate   TEXT NOT NULL",
                             "Seller       TEXT NOT NULL",
                             "ProfitSplit  TEXT NOT NULL",
                             "PriceEach    TEXT NOT NULL",
                             "OldCount     INTEGER NOT NULL",
                             "NewCount     INTEGER NOT NULL",
                             "Tax          TEXT NOT NULL")

#   Anonymous Donations of cash
Donations = Table("Donations", "Date       TEXT NOT NULL",
                               "Amount     TEXT NOT NULL")

#   Expiration events
#     If the expired item has multiple sellers, we use multiple rows.
ExpiryEvents = Table("ExpiryEvent", "ItemName     TEXT NOT NULL",
                                    "Date         TEXT NOT NULL",
                                    "StockDate    TEXT NOT NULL",
                                    "ExpiryDate   TEXT NOT NULL",
                                    "Seller       TEXT NOT NULL",
                                    "ProfitSplit  TEXT NOT NULL",
                                    "PriceEach    TEXT NOT NULL",
                                    "Count        INTEGER NOT NULL",
                                    "Tax          TEXT NOT NULL")

# Statistics
#   For keeping track of interesting data.
#   Some entries, such as "transactions", are not cumulative but rather
#   are the number of transactions since the last record.
Statistics = Table("StatisticsRecord", "Date         TEXT NOT NULL",
                                       "AvgBalance   TEXT",
                                       "ExpectedCash TEXT",
                                       "Transactions INTEGER")

def initialize_test_database():
    """This function should only be called on an empty new database. This
       function should also be where you create fake users/items for testing."""
    with sql.connect(sql_database) as conn:
        Users.create(conn)
        Items.create(conn)
        Sellers.create(conn)
        Purchases.create(conn)
        Transfers.create(conn)
        BalanceChanges.create(conn)
        Stocking.create(conn)
        Donations.create(conn)
        ExpiryEvents.create(conn)
        Statistics.create(conn)

        # Now we will populate the Users and Items tables with some fake users
        # and items.
        add_user("jrmole", "jrmole@blacker.caltech.edu")
        add_user("socialmole", "socialmole@blacker.caltech.edu")
        add_user("mole", "mole@blacker.caltech.edu")
        add_user("srmole", "srmole@blacker.caltech.edu")

        add_item("snapple", {"jrmole": '0.50', "srmole": '0.50'},
                 24, '1.23', '0.00', 52, 'A Juicy Beverage')
        add_item("Lorem ipsum", {"mole": '0.95'}, 2, '1.55', '0.05', 24,
                 """Lorem ipsum dolor sit amet, consectetur adipisicing elit""")
        add_item("Test item", {"mole": '0.95'}, 123, '1.23', '0.05', 24,
                 """Lorem ipsum dolor sit amet, consectetur adipisicing elit""")
    return True

def delete_test_database():
    """Delete the database. Be careful! Also rebuilds the database."""
    import os
    os.remove(sql_database)
    return initialize_test_database()

def checkout(itemname, buyer, count):
    """Buyer checkouts any amount of a single item."""
    date = datetime.datetime.now()
    profit_split_by_sellers = get_fraction_by_sellers(itemname)
    current_count, price_each, stockdate, expiry, _ = get_item_info(itemname)
    total_price = round_price(Decimal(price_each) * count)

    with sql.connect(sql_database) as conn:
        tax = Items.select_one(conn, "Name=?", itemname).Tax

        # Subtract count from the item. If count is zero, then remove the item
        # record. If the count goes below zero, we have an error. Do not record
        # the transaction and return False.
        new_count = current_count - count
        if new_count < 0:
            return False
        elif new_count == 0:
            Items.delete(conn, "Name=?", itemname)
            Sellers.delete(conn, "ItemName=?", itemname)
        else:
            Items.update(conn, "Count=?", "Name=?", new_count, itemname)

        # Subtract money from buyer
        ## Todo: use demical
        Users.update(conn, "Balance=Balance-?", "Name=?",
                     str(total_price), buyer)

        for seller, profit_split in profit_split_by_sellers.items():
            # Record the transaction
            Purchases.insert(conn, itemname, date, stockdate, expiry,
                                          buyer, seller, profit_split,
                                          price_each, count, tax)
            # Add money to seller
            Users.update(conn, "Balance=Balance+?", "Name=?",
                         str(round_price(total_price * Decimal(profit_split))),
                         seller)
    return True


def add_item(itemname, sellers, count, price_each, tax, expiry_time_in_weeks,
             description=''):
    """Adds an item as being in-stock and stocked by certain sellers.
       Returns True if successful."""
    assert isinstance(count, int)
    assert isinstance(expiry_time_in_weeks, int)
    price_each = round_price(Decimal(price_each))
    tax = Decimal(tax)
    assert (sum(map(Decimal, sellers.values())) + tax == Decimal('1.00'))

    duration = datetime.timedelta(weeks=expiry_time_in_weeks)
    stockdate = datetime.datetime.now()
    expirydate = stockdate + duration

    with sql.connect(sql_database) as conn:
        Items.insert(conn, itemname, count, str(price_each), str(tax),
                                 stockdate, expirydate, description)
        for seller, profit_split in sellers.items():
            Sellers.insert(conn, itemname, seller, profit_split)
            Stocking.insert(conn,
                            itemname, stockdate, stockdate, expirydate,
                            seller, profit_split, str(price_each), 0,
                            count, str(tax))
    return True

def add_user(username, email, uid=0):
    """Creates a new user and inserts into the database.
       Returns True if successful"""
    assert isinstance(uid, int)
    with sql.connect(sql_database) as conn:
        balance = Decimal('0.00')
        joindate = datetime.datetime.now()
        Users.insert(conn, username, email, str(balance), uid, joindate)
    return True

def get_all_stock():
    """Returns all items stocked and all the associated data."""
    with sql.connect(sql_database) as conn:
        return list(Items.select(conn, None))

def get_fraction_by_sellers(itemname):
    """Returns a dictionary with sellers as keys, profit fractions as values."""
    with sql.connect(sql_database) as conn:
        rows = Sellers.select(conn, "ItemName=?", itemname)
    return dict((row.Seller, row.ProfitSplit) for row in rows)

def get_all_sellers():
    """Returns a dictionary with item names as keys, seller lists as values."""
    with sql.connect(sql_database) as conn:
        rows = Sellers.select(conn, None)
    sellers_by_item = {}
    for row in rows:
        if row.ItemName in sellers_by_item:
            sellers_by_item[row.ItemName].append(row.Seller)
        else:
            sellers_by_item[row.ItemName] = [row.Seller]
    return sellers_by_item

def get_user_stock(username):
    """Returns all item names which list the given username as a seller."""
    rows = []
    with sql.connect(sql_database) as conn:
        for row in Sellers.select(conn, "Seller=?", username):
            rows.append(row.ItemName)
    return rows

def get_usernames():
    """Returns a list of all usernames."""
    names = []
    with sql.connect(sql_database) as conn:
        for row in Users.select(conn, None):
            names.append(row.Name)
    return names

def get_username(username):
    """Returns the information on a username if it exists, otherwise False."""
    with sql.connect(sql_database) as conn:
        t = Users.select_one(conn, "Name=?", username)
    return t

def get_store_info(username):
    """This request returns all the information needed when store.html loads.
       This includes the username, all in-stock items, all items being sold by
       the user, and past transactions of that user."""
    userinfo = get_username(username)
    if not username:
        return False
    all_stock = get_all_stock()
    usernames = get_usernames()
    user_stock = get_user_stock(username)
    sellers_by_item = get_all_sellers()
    transactions = get_user_transactions(username)
    return (userinfo, all_stock, usernames, user_stock,
            sellers_by_item, transactions)

def get_item_info(itemname):
    """Returns count, price, stock date, expiry date, description of an item."""
    with sql.connect(sql_database) as conn:
        row = Items.select_one(conn, "Name=?", itemname)
    return row.Count, row.Price, row.StockDate, row.ExpiryDate, row.Description

def addremove_item(itemname, count_to_add):
    """Modifies stock by altering item count only. Returns True if
       successful."""
    assert isinstance(count_to_add, int)
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        row = Items.select_one(conn, "Name=?", itemname)
        _, count, price, tax, stockdate, expirydate, _ = row
        new_count = count + count_to_add
        if new_count < 0:
            return False
        
        rows = Sellers.select(conn, "ItemName=?", itemname)
        profit_splits_by_seller = dict((row.Seller, row.ProfitSplit)
                                       for row in rows)
        
        if new_count == 0:
            Sellers.delete(conn, "ItemName=?", itemname)
            Items.delete(conn, "ItemName=?", itemname)
        else:
            Items.update(conn, "Count=?", "Name=?", new_count, itemname)

        for seller, profit_split in profit_splits_by_seller.items():
            # Record this stock change
            Stocking.insert(conn, itemname, date, stockdate, expirydate,
                                seller, profit_split, price, count,
                                new_count, tax)
    return True

def check_expired_stock():
    """Removes all stock which has expired and records this."""
    pass # todo

def get_user_transactions(username):
    """Returns all transactions associated with a username."""
    with sql.connect(sql_database) as conn:
        purchases = Purchases.select(conn, "Buyer=? OR Seller=? ORDER BY Date",
                                     username, username)
        transfers = Transfers.select(conn, "Sender=? OR Receiver=? "
                                     "ORDER BY Date", username, username)
        balances = BalanceChanges.select(conn, "User=? ORDER BY Date", username)
        stocks = Stocking.select(conn, "Seller=? ORDER BY Date", username)
        expiries = ExpiryEvents.select(conn, "Seller=? ORDER BY Date", username)
    return purchases, transfers, balances, stocks, expiries

def transfer_funds(sender, receiver, amount):
    """Transfers any nonzero amount of funds from one user to another.
       Returns True if successful."""
    amount = price(amount)
    assert amount > 0
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        sender_balance = Users.select_one(conn, "Name=?", (sender,)).Balance
        receiver_balance = Users.select_one(conn, "Name=?", (receiver,)).Balance
        
        Users.update(conn, "Balance=?", "Name=?",
                     str(sender_balance - amount), sender)
        Users.update(conn, "Balance=?", "Name=?",
                     str(receiver_balance + amount), receiver)
        Transfers.insert(conn, date, sender, receiver, str(amount))
    return True

def donate(amount):
    """Records an anonymous donation of cash. Returns True if successful."""
    amount = price(amount)
    assert amount > 0
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        Donations.insert(conn, date, amount)
    return True

def get_total_cash():
    """The expected amount of cash in Limbo is the sum of all user balances
       and all donations."""
    with sql.connect(sql_database) as conn:
        total_balances = sum(Decimal(user.Balance)
                             for user in Users.select(conn, None))
        total_donations = sum(Decimal(donation.Amount)
                              for donation in Donations.select(conn, None))
        return total_balances + total_donations

def change_balance(username, amount):
    """Deposit or withdraw some amount."""
    amount = price(amount)
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        if amount == 0:
            return True
        else:
            Users.update(conn, "Balance=Balance+?", "Name=?",
                         str(amount), username)
        BalanceChanges.insert(conn, date, username, str(amount))
    return True

def main():
    # These are the allowed actions of cgi requests.
    actions = {
        "add_user":     add_user,
        "usernames":    get_usernames,
        "username":     get_username,
        "store_info":   get_store_info,
        "add_item":     add_item,
        "addremove":    addremove_item,
        "item_info":    get_item_info,
        "checkout":     checkout,
        "transactions": get_user_transactions,
        "transfer":     transfer_funds,
        "donate":       donate,
        "cash":         get_total_cash,
        "balance":      change_balance,
        # remove the following line in production
        "delete_test_database": delete_test_database,
    }
    # Get cgi arguments
    form = cgi.FieldStorage()
    action = form.getfirst("action", "")
    # If no valid action is provided, don't do anything.
    if action not in actions:
        return
    function = actions[action]
    # What is about to happen uses CPython-specific code to find the arguments
    # in the function and assign them based on name.
    argnames = function.__code__.co_varnames[:function.__code__.co_argcount]
    arguments_to_apply = {}
    for argname in argnames:
        arguments_to_apply[argname] = eval(form.getfirst(argname, None))
    # Print the return value to send to the client.
    print(function(**arguments_to_apply))

main()
