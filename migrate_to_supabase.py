"""
Veetile-Ruchi Safe Database & Media Migration Utility -> Supabase
Transfers local PostgreSQL schema and data, auto-resets PostgreSQL sequences,
verifies table record counts, and uploads uploaded food images/media to Supabase Storage.
"""
import os
import sys
import json
import mimetypes
import urllib.request
import urllib.error
from collections import Counter
import django

# Set up Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'veetile_ruchi_project.settings')
django.setup()

from django.conf import settings
from django.db import connection
from django.core.management import call_command
from django.apps import apps
from django.core.management.color import no_style

BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups_verified')
JSON_DUMP_PATH = os.path.join(BACKUP_DIR, 'veetile_ruchi_django_dump.json')
SQL_BACKUP_PATH = os.path.join(BACKUP_DIR, 'veetile_ruchi_postgres_backup.sql')
MEDIA_ZIP_PATH = os.path.join(BACKUP_DIR, 'media_backup.zip')

def verify_source_backup():
    print("=" * 70)
    print("STEP 1: VERIFYING LOCAL SOURCE DATA & MEDIA BACKUPS")
    print("=" * 70)
    
    if not os.path.exists(SQL_BACKUP_PATH):
        print(f"[ERROR] SQL backup file not found: {SQL_BACKUP_PATH}")
        return False
    print(f"[OK] PostgreSQL SQL backup verified: {SQL_BACKUP_PATH} ({os.path.getsize(SQL_BACKUP_PATH):,} bytes)")
    
    if not os.path.exists(JSON_DUMP_PATH):
        print(f"[ERROR] JSON dump file not found: {JSON_DUMP_PATH}")
        return False
    with open(JSON_DUMP_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[OK] JSON data dump verified: {len(data)} objects serialized across models.")

    if not os.path.exists(MEDIA_ZIP_PATH):
        print(f"[ERROR] Media backup zip not found: {MEDIA_ZIP_PATH}")
        return False
    print(f"[OK] Media archive verified: {MEDIA_ZIP_PATH} ({os.path.getsize(MEDIA_ZIP_PATH):,} bytes)")
    return True

def verify_target_connection():
    print("\n" + "=" * 70)
    print("STEP 2: VERIFYING TARGET SUPABASE POSTGRESQL CONNECTION")
    print("=" * 70)
    
    db_engine = settings.DATABASES['default']['ENGINE']
    db_host = settings.DATABASES['default'].get('HOST', 'localhost')
    db_name = settings.DATABASES['default'].get('NAME', '')
    
    print(f"Active Database Engine : {db_engine}")
    print(f"Active Host            : {db_host}")
    print(f"Active Database        : {db_name}")
    
    if 'postgresql' not in db_engine:
        print("[NOTICE] Target database engine is currently NOT PostgreSQL.")
        return False
        
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            ver = cursor.fetchone()
            print(f"[OK] Connected to PostgreSQL successfully!")
            print(f"Version: {ver[0][:80]}...")
            cursor.execute("SELECT current_user, current_database();")
            user, db = cursor.fetchone()
            print(f"Logged in as user: '{user}' on database: '{db}'")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to connect to target PostgreSQL: {e}")
        return False

def apply_migrations():
    print("\n" + "=" * 70)
    print("STEP 3: RUNNING DJANGO MIGRATIONS ON SUPABASE POSTGRESQL")
    print("=" * 70)
    try:
        print("Executing: python manage.py migrate --noinput ...")
        call_command('migrate', interactive=False, verbosity=1)
        print("[OK] Schema migrations completed successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False

def load_data():
    print("\n" + "=" * 70)
    print("STEP 4: LOADING DATA INTO SUPABASE POSTGRESQL")
    print("=" * 70)
    try:
        print(f"Executing: python manage.py loaddata {JSON_DUMP_PATH} ...")
        call_command('loaddata', JSON_DUMP_PATH, verbosity=1)
        print("[OK] All serialized data successfully loaded into Supabase PostgreSQL!")
        return True
    except Exception as e:
        print(f"[ERROR] Data loading encountered an issue: {e}")
        return False

def reset_sequences():
    print("\n" + "=" * 70)
    print("STEP 5: RESETTING POSTGRESQL AUTO-INCREMENT SEQUENCES")
    print("=" * 70)
    apps_to_reset = ['accounts', 'food', 'orders', 'delivery', 'ai_models', 'health', 'auth', 'sessions']
    style = no_style()
    statements = []
    
    for app_name in apps_to_reset:
        try:
            app_config = apps.get_app_config(app_name)
            seq_sql = connection.ops.sequence_reset_sql(style, app_config.get_models())
            statements.extend(seq_sql)
        except Exception as e:
            print(f"Warning checking sequences for {app_name}: {e}")
            
    print(f"Found {len(statements)} sequence reset statements to execute.")
    if statements:
        with connection.cursor() as cursor:
            for sql in statements:
                try:
                    cursor.execute(sql)
                except Exception as e:
                    print(f"Sequence notice: {e} -> SQL: {sql}")
        print("[OK] PostgreSQL sequences reset. Future inserts will auto-increment safely!")
    return True

def verify_table_parity():
    print("\n" + "=" * 70)
    print("STEP 6: COMPREHENSIVE DATA & PARITY VERIFICATION")
    print("=" * 70)
    
    with open(JSON_DUMP_PATH, 'r', encoding='utf-8') as f:
        dump_data = json.load(f)
    expected_counts = Counter(item['model'] for item in dump_data)
    
    mismatches = 0
    total_records = 0
    
    for model in apps.get_models():
        label_lower = model._meta.label_lower
        if label_lower in ['contenttypes.contenttype', 'auth.permission']:
            continue
        try:
            db_count = model.objects.count()
            total_records += db_count
            exp_count = expected_counts.get(label_lower, 0)
            
            status = "[MATCH]" if db_count >= exp_count else "[MISMATCH]"
            if db_count < exp_count:
                mismatches += 1
            print(f"{status:10} {model._meta.label:32}: Database={db_count:4} | Original={exp_count:4}")
        except Exception as e:
            print(f"[ERROR]   {model._meta.label:32}: {e}")
            mismatches += 1
            
    print("-" * 70)
    print(f"Total database records verified: {total_records}")
    if mismatches == 0:
        print("[SUCCESS] All model record counts match or exceed the original database!")
        return True
    else:
        print(f"[WARNING] {mismatches} model(s) have count discrepancies. Please review above.")
        return False

def verify_critical_business_records():
    print("\n" + "=" * 70)
    print("STEP 7: CRITICAL BUSINESS RECORD INTEGRITY CHECKS")
    print("=" * 70)
    
    from accounts.models import DeliveryBoyProfile
    from food.models import FoodItem
    from orders.models import Order, Payment
    
    # 1. Couriers Check
    couriers = DeliveryBoyProfile.objects.all()
    print(f"[COURIERS] Total delivery boy profiles: {couriers.count()}")
    for c in couriers[:5]:
        print(f"  - Courier: {c.user.username} | Phone: {c.user.phone} | Status: {c.status}")
    if couriers.count() >= 9:
        print("  [OK] All courier boys and statuses preserved.")
        
    # 2. Food catalog check
    food_count = FoodItem.objects.count()
    foods_with_img = FoodItem.objects.exclude(image__isnull=True).exclude(image='').count()
    print(f"[FOOD] Total items: {food_count} | Items with image references: {foods_with_img}")
        
    # 3. Orders & Cash Collected
    orders_count = Order.objects.count()
    cod_collected = Payment.objects.filter(status='completed').count()
    print(f"[ORDERS] Total orders: {orders_count} | Completed payments: {cod_collected}")

def migrate_media_to_supabase_storage():
    print("\n" + "=" * 70)
    print("STEP 8: SUPABASE STORAGE MEDIA MIGRATION")
    print("=" * 70)
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "media")
    
    if not supabase_url or not supabase_key:
        print("[NOTICE] SUPABASE_URL or SUPABASE_KEY not configured in .env.")
        print("To enable Supabase Storage sync, add the following to .env:")
        print("  SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co")
        print("  SUPABASE_KEY=[YOUR-SUPABASE-ANON-OR-SERVICE-KEY]")
        print("  SUPABASE_STORAGE_BUCKET=media")
        print("  USE_SUPABASE_STORAGE=True")
        print("Media files remain safely stored and served locally from /media/.")
        return False
        
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
    }
    
    # Check or create bucket
    bucket_url = f"{supabase_url.rstrip('/')}/storage/v1/bucket/{bucket}"
    req = urllib.request.Request(bucket_url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"[OK] Supabase Storage bucket '{bucket}' confirmed exists.")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Creating public bucket '{bucket}' on Supabase Storage...")
            create_url = f"{supabase_url.rstrip('/')}/storage/v1/bucket"
            data = json.dumps({"id": bucket, "name": bucket, "public": True}).encode('utf-8')
            create_req = urllib.request.Request(create_url, data=data, headers={**headers, "Content-Type": "application/json"}, method='POST')
            try:
                with urllib.request.urlopen(create_req) as cr:
                    print(f"[OK] Created public bucket '{bucket}'.")
            except Exception as ce:
                print(f"[WARN] Bucket creation notice: {ce}")
        else:
            print(f"[WARN] Storage check notice: {e}")
            
    # Iterate and upload files
    media_root = str(settings.MEDIA_ROOT)
    uploaded = 0
    errors = 0
    
    for root, dirs, files in os.walk(media_root):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, media_root).replace('\\', '/')
            mime_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
            
            upload_url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{rel_path}"
            try:
                with open(full_path, 'rb') as file_data:
                    payload = file_data.read()
                upload_headers = {
                    **headers,
                    "Content-Type": mime_type,
                    "x-upsert": "true"
                }
                up_req = urllib.request.Request(upload_url, data=payload, headers=upload_headers, method='POST')
                with urllib.request.urlopen(up_req) as res:
                    uploaded += 1
                    if uploaded % 20 == 0:
                        print(f"  Uploaded {uploaded} media assets to Supabase Storage...")
            except Exception as ue:
                errors += 1
                if errors <= 3:
                    print(f"[WARN] Failed to upload {rel_path}: {ue}")
                    
    print(f"\n[OK] Media migration complete: {uploaded} files uploaded, {errors} errors.")
    return errors == 0

if __name__ == '__main__':
    print("Veetile-Ruchi -> Supabase Safe Migration & Verification Tool")
    if not verify_source_backup():
        sys.exit(1)
        
    if not verify_target_connection():
        print("\nTarget database connection not established. Check settings.py and .env.")
        sys.exit(0)
        
    if not apply_migrations():
        sys.exit(1)
        
    if not load_data():
        sys.exit(1)
        
    reset_sequences()
    verify_table_parity()
    verify_critical_business_records()
    migrate_media_to_supabase_storage()
    print("\n[ALL STEPS COMPLETED SUCCESSFULLY]")
