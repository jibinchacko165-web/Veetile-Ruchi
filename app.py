import os
import sys

# Ensure project directory and bundled lib directory are in Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_dir = os.path.join(current_dir, 'lib')

if os.path.isdir(lib_dir) and lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'veetile_ruchi_project.settings')

# Import WSGI application
from veetile_ruchi_project.wsgi import application

if __name__ == '__main__':
    port = int(os.environ.get('X_ZOHO_CATALYST_LISTEN_PORT', os.environ.get('PORT', 9000)))
    print(f"Starting Veetile-Ruchi AppSail server on 0.0.0.0:{port}...", flush=True)
    try:
        from gunicorn.app.base import BaseApplication

        class StandaloneApplication(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            'bind': f'0.0.0.0:{port}',
            'workers': 2,
            'threads': 2,
            'worker_class': 'gthread',
            'timeout': 120,
            'accesslog': '-',
            'errorlog': '-',
        }
        StandaloneApplication(application, options).run()
    except Exception as e:
        print(f"Gunicorn fallback ({e}), serving with standard wsgiref on 0.0.0.0:{port}...", flush=True)
        from wsgiref.simple_server import make_server
        server = make_server('0.0.0.0', port, application)
        server.serve_forever()
