# Veetile-Ruchi (വീട്ടിലെ രുചി)
**Authentic Kerala Homemade Food Delivery Platform**

Veetile-Ruchi is a full-featured online food ordering and delivery system connecting local home chefs in Kerala with customers. Built with Django and PostgreSQL, the platform features multi-role dashboards (Customer, Home Chef, Courier Delivery Boy, Staff/Admin), AI-driven delivery time predictions, real-time GPS courier delivery tracking, OpenStreetMap/Leaflet delivery tracking with straight-line distance estimation, nutritional tracking, and health profiling.

---

## 1. Tech Stack & Requirements

- **Python**: 3.10 – 3.12 (Tested on Python 3.12)
- **Django**: 4.2 LTS (`Django>=4.2,<5.0`)
- **Primary Database**: PostgreSQL 14+ (Database: `veetile_ruchi`)
- **Python DB Drivers**: `psycopg` (v3) / `psycopg2-binary`
- **Mapping & Geolocation**:
  - Map Display: **Leaflet.js** (Local static assets, zero CDN dependencies for offline reliability)
  - Map Tiles: **OpenStreetMap** (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`)
  - Geolocation: **HTML5 Browser Geolocation API** (High Accuracy)
  - Reverse Geocoding: OpenStreetMap Nominatim with local Kerala preset fallbacks and server caching
- **Machine Learning & Analytics**:
  - Scikit-Learn (Random Forest delivery time predictor)
  - NumPy, Pandas, SciPy

---

## 2. Architecture & Design Principles

1. **Leaflet + OpenStreetMap Only**:
   - Zero Google Maps dependency. Google Maps scripts, API keys, and SDK calls have been completely removed.
   - Map tiles are served via OpenStreetMap with automated tile failover.
2. **Accurate Distance & Transit Estimation**:
   - Haversine straight-line distance calculations provide reliable, consistent distance measurements and transit time estimates without third-party routing service failure risks.
3. **Strict Separation of Hub & Courier Live GPS**:
   - Central Kitchen Hub coordinates (`Kanjirappally, Kottayam: 9.5564, 76.7909`) represent the physical preparation facility.
   - Courier live GPS coordinates are continuously recorded from the courier's device during active transit and displayed on the customer's live tracking map.
4. **Data Integrity & Relational Safety**:
   - Clean foreign keys across User, CustomerProfile, ChefProfile, DeliveryBoyProfile, FoodItem, Order, and DeliveryAssignment.
   - Automatic fallback images for food items where media files are missing.

---

## 3. Installation & Setup Guide

### Step 1: Clone the Repository
```bash
git clone https://github.com/jibinchacko165-web/Veetile-Ruchi.git
cd Veetile-Ruchi
```

### Step 2: Create and Activate a Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure PostgreSQL
1. Ensure the PostgreSQL service is active on your machine.
2. Create the PostgreSQL database:
```sql
CREATE DATABASE veetile_ruchi;
```
3. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
4. Update `.env` with your PostgreSQL credentials:
```env
DB_NAME=veetile_ruchi
DB_USER=postgres
DB_PASSWORD=your_postgresql_password
DB_HOST=localhost
DB_PORT=5432
```

### Step 5: Run Database Migrations
```bash
python manage.py migrate
```

### Step 6: Verify Database Connection & Seed Data (Optional)
```bash
# Seed standard courier records
python manage.py seed_couriers

# Run system checks
python manage.py check
```

### Step 7: Run the Development Server
```bash
python manage.py runserver
```
Access the application at `http://127.0.0.1:8000/`.

---

## 4. Environment Variables Reference

Configure these settings in your `.env` file (do not commit `.env` to Git):

| Variable | Description | Default |
| :--- | :--- | :--- |
| `SECRET_KEY` | Django secret cryptographic key | Auto-generated |
| `DEBUG` | Enable debug mode during development | `True` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames | `127.0.0.1,localhost` |
| `DB_NAME` | PostgreSQL database name | `veetile_ruchi` |
| `DB_USER` | PostgreSQL user | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | Required |
| `DB_HOST` | PostgreSQL host address | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `MAP_TILE_URL` | Map tile template URL | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` |
| `MAP_TILE_ATTRIBUTION` | Legal tile attribution markup | OpenStreetMap contributors |

---

## 5. Live GPS Tracking Workflow

### Customer GPS
- Handled via `navigator.geolocation.getCurrentPosition` with `enableHighAccuracy: true`.
- For desktop browsers or denied permissions, customers can click on the interactive Leaflet map to pinpoint their exact location or type an address notes fallback.
- Latitude and Longitude are stored on the `Order` record upon checkout.

### Courier Live GPS
- Couriers broadcast GPS coordinates using `navigator.geolocation.watchPosition` on active delivery pages.
- Coordinates are transmitted via POST to `/delivery/api/update-profile-gps/` and `/delivery/api/track-order/<order_id>/`.
- Server records breadcrumb updates in `GPSLocationTracking` models.
- If the courier's location is older than 5 minutes, the customer tracking UI highlights a "Stale Location Warning" and displays the last known timestamp.

---

## 6. Running Tests

The test suite covers models, forms, views, APIs, authentication, permissions, and GPS delivery tracking.

```bash
# Run all core app unit tests
python manage.py test accounts food orders delivery health ai_models tests.test_profile_validation --keepdb

# Run the comprehensive GPS delivery tracking test suite
python manage.py test tests.test_gps_delivery_tracking --keepdb

# Run full test suite with fast DB reuse
python manage.py test --keepdb
```

---

## 7. Common Errors & Troubleshooting

- **`psycopg` / `psycopg2` Connection Refused**:
  - Ensure the PostgreSQL service is running (`net start postgresql-x64-16` on Windows or `sudo systemctl start postgresql` on Linux).
  - Verify password and port 5432 in `.env`.
- **Browser Geolocation Denied / Timeout**:
  - The HTML5 Geolocation API requires a secure context (`https://` or `localhost` / `127.0.0.1`).
  - Ensure browser permissions allow location access for `localhost`.

---

## 8. License & Credits

- Developed for **Veetile-Ruchi** home food delivery.
- Map tiles: &copy; [OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
- Icons: FontAwesome 6 Free.
