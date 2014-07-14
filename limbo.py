#!/usr/bin/python3
# Common client-side python routines

# To debug the front-end can be a bit difficult. It's recommended to open the
# developer console of your web browser (ctrl+shift+J in firefox)

from browser import doc, alert, ajax, window

class Keycode():
    enter = 13
    delete = 46

timeout = 4

def timeout_error():
    notify("Server didn't reply after %s seconds" % limbo.timeout)

# We want to make sure that there is a field with id "result" which we can put
# error text in (or possibly other notifications)
try:
    doc["result"]
    def notify(text):
        doc["result"].html = text
except:
    def notify(text):
        print("Notifications won't work")

def request(async, on_complete=None, **kwargs):
    """All calls go to cgi-bin/limbo.py; exactly what is done depends on the
       arguments passed. """
    req = ajax.ajax()
    def callback(req):
        on_complete(eval(req.text))
    if on_complete:
        req.bind('complete', callback)
    req.set_timeout(timeout, timeout_error)
    req.open('POST', 'cgi-bin/limbo-cgi.py', async=async)
    req.set_header('content-type', 'application/x-www-form-urlencoded')
    req.send(kwargs)

def async_request(on_complete=None, **kwargs):
    request(async=True, on_complete=on_complete, **kwargs)
    
def sync_request(on_complete=None, **kwargs):
    request(async=False, on_complete=on_complete, **kwargs)

def redirect(url, **kwargs):
    window.location.href = (url + '?' +
        '&'.join('%s=%s' % (key, value) for key, value in kwargs.items()))

# The below gets called on import.
