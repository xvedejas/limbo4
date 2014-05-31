#!/usr/bin/python3
# Backend to Limbo4. This is called as a cgi script.

import cgi, cgitb
cgitb.enable()
form = cgi.FieldStorage()

#import sqlite3
#conn = sqlite3.connect('limbo4.db')

inventory = ["eggs", "ham", "spam", "SPAM"]
usernames = ["xander", "jrmole"]

def get_inventory():
    return inventory

def get_usernames():
    return usernames

def is_username(username):
    return username.lower() in usernames

def login(username):
    """Arguments:
            username
       Return values:
            success: boolean
            username: accepted username string, lowercase
    """
    username = username.lower()
    return (username in usernames, username)

actions = {
    "login": login,
    "get_usernames": get_usernames,
    "is_username": is_username,
}

def main():
    # CGI scripts must start with this.
    print("Content-Type: text/html\n")
    action = form.getfirst("action", "")
    # If no valid action is provided, don't do anything.
    if action not in actions:
        return
    function = actions[action]
    arguments_to_apply = {}
    # What is about to happen uses CPython-specific code.
    for varname in function.__code__.co_varnames:
        arguments_to_apply[varname] = form.getfirst(varname, None)
    # Print the return value
    print(function(**arguments_to_apply))

main()
