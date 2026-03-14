import sys
import urllib.request
import urllib.error
import traceback

def fetch(url):
    try:
        r = urllib.request.urlopen(url, timeout=10)
        print('STATUS', r.getcode())
        content = r.read().decode('utf-8', errors='replace')
        print(content)
    except urllib.error.HTTPError as he:
        try:
            body = he.read().decode('utf-8', errors='replace')
            print('HTTP ERROR BODY:')
            print(body)
        except Exception:
            pass
        traceback.print_exc()
    except Exception:
        traceback.print_exc()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python fetch_url.py <url>')
        sys.exit(1)
    fetch(sys.argv[1])
