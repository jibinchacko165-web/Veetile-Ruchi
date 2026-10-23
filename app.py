#!/usr/bin/env python3
"""
Veetile-Ruchi Resilient AppSail Entrypoint
Optimized for Zoho Catalyst persistent cloud containers.
Binds to X_ZOHO_CATALYST_LISTEN_PORT immediately to pass health checks within 10s.
"""
import os
import sys
import logging
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler

# 1. Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_dir = os.path.join(current_dir, 'lib')

if os.path.isdir(lib_dir) and lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'veetile_ruchi_project.settings')
os.environ.setdefault('PYTHONUNBUFFERED', '1')

port_str = os.environ.get('X_ZOHO_CATALYST_LISTEN_PORT', os.environ.get('PORT', '9000'))
try:
    port = int(port_str)
except ValueError:
    port = 9000

print(f"=== Veetile-Ruchi AppSail Initializing ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Working Directory: {current_dir}", flush=True)
print(f"Target Port: {port}", flush=True)

django_app = None
django_error = None

def get_django_app():
    global django_app, django_error
    if django_app is not None:
        return django_app
    if django_error is not None:
        return None
    try:
        from veetile_ruchi_project.wsgi import application
        django_app = application
        print("Django WSGI application initialized successfully.", flush=True)

        # Ensure database schema is 100% up to date on boot
        try:
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            print("Database migrations verified and up to date.", flush=True)
            # Safeguard: if database has 0 users, restore from initial_data_backup.json
            from accounts.models import User
            backup_fixture = os.path.join(current_dir, 'initial_data_backup.json')
            if not User.objects.exists() and os.path.isfile(backup_fixture):
                print(f"Empty database detected. Restoring data from {backup_fixture}...", flush=True)
                call_command('loaddata', backup_fixture)
                print("Database data restoration completed successfully.", flush=True)
        except Exception as mig_err:
            print(f"Notice during startup database check: {mig_err}", flush=True)

        return django_app
    except Exception as exc:
        import traceback
        django_error = traceback.format_exc()
        print(f"FATAL: Django WSGI initialization failed:\n{django_error}", flush=True)
        return None

# Pre-warm Django in background or immediately
try:
    get_django_app()
except Exception as e:
    print(f"Warning: Pre-warm deferred ({e})", flush=True)

class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True

class AppSailRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        sys.stdout.write(f"[HTTP] {self.client_address[0]} - {format % args}\n")
        sys.stdout.flush()

    def get_environ(self):
        env = super().get_environ()
        env['raw_headers_list'] = list(self.headers.items())
        return env

def resilient_wsgi_app(environ, start_response):
    # AppSail public gateway terminates SSL and exposes apps over HTTPS (:443)
    environ['wsgi.url_scheme'] = 'https'
    environ['HTTP_X_FORWARDED_PROTO'] = 'https'
    environ['SERVER_PORT'] = '443'
    if environ.get('HTTP_HOST', '').endswith(':443'):
        environ['HTTP_HOST'] = environ['HTTP_HOST'][:-4]

    path = environ.get('PATH_INFO', '')
    if path in ('/health', '/health/'):
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [b'{"status": "ok", "app": "veetile-ruchi"}']

    if path == '/test-post':
        cl = environ.get('CONTENT_LENGTH', '')
        stream = environ.get('wsgi.input')
        body = b''
        if cl and cl.isdigit() and int(cl) > 0:
            body = stream.read(int(cl))
        import json
        headers_dump = {k: str(v) for k, v in environ.items() if k.startswith('HTTP_') or 'CONTENT' in k or 'LENGTH' in k}
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps({"cl": cl, "body": body.decode('utf-8', errors='ignore'), "raw_headers": environ.get('raw_headers_list', []), "headers": headers_dump}).encode('utf-8')]

    # Normalize CGI content variables for WSGI compliance
    if not environ.get('CONTENT_TYPE') and environ.get('HTTP_CONTENT_TYPE'):
        environ['CONTENT_TYPE'] = environ['HTTP_CONTENT_TYPE']
    if not environ.get('CONTENT_LENGTH') and environ.get('HTTP_CONTENT_LENGTH'):
        environ['CONTENT_LENGTH'] = environ['HTTP_CONTENT_LENGTH']

    app = get_django_app()
    if app is not None:
        return app(environ, start_response)

    start_response('500 Internal Server Error', [('Content-Type', 'text/plain; charset=utf-8')])
    return [f"Veetile-Ruchi Diagnostic Traceback:\n\n{django_error}".encode('utf-8')]

if __name__ == '__main__':
    print(f"Actively binding to 0.0.0.0:{port}...", flush=True)
    try:
        httpd = make_server('0.0.0.0', port, resilient_wsgi_app, server_class=ThreadingWSGIServer, handler_class=AppSailRequestHandler)
        print(f"Veetile-Ruchi server actively listening on 0.0.0.0:{port} (Ready for traffic).", flush=True)
        httpd.serve_forever()
    except Exception as e:
        print(f"FATAL: Could not bind or run server: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
