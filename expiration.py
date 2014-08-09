#!/usr/bin/python
# Checks limbo stock for expired goods.
from server import sql_database, Items, ExpiryEvents, Sellers
import sqlite3 as sql
import datetime

if __name__ == '__main__':
    with sql.connect(sql_database) as conn:
        now = datetime.datetime.now()
        items = Items.select(conn, "ExpiryDate < ?", now)
        for item in items:
            print("Deleting expired item %s." % item.Name)
            seller_records = Sellers.select(conn, "ItemName=?", item.Name)
            # Record the ExpiryEvent
            for seller_record in seller_records:
                ExpiryEvents.insert(conn, item.Name, now, item.StockDate,
                                    item.ExpiryDate, seller_record.Seller,
                                    seller_record.ProfitSplit,
                                    item.Price, item.Count, item.Tax)
        # Delete all expired items from Items
        Items.delete(conn, "ExpiryDate < ?", now)
    exit(0)
