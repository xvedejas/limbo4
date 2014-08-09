import sqlite3 as sql
import datetime
# All prices should be manipulated as Decimal values roudned to two places after
# the decimal point. All fractions should also be Decimal values.
# Use str(decimal_value) to get the representation to put in the database.
import decimal
from decimal import Decimal
decimal.getcontext().prec = 6
from collections import namedtuple
path_to_limbo = '/srv/http/limbo4/'

# There's a decent sqlite tutorial here:
# http://zetcode.com/db/sqlitepythontutorial/
sql_database = path_to_limbo + 'data/limbo4.db'

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
