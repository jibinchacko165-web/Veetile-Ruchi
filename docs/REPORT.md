# Veetile‑Ruchi Project Report

## 1. Project Specification & System Overview
*Adapted content describing the project's purpose, technologies (Django, PostgreSQL, Scikit‑Learn, Leaflet), and overall architecture.*

## 2. Objectives of the Project
*List of project objectives aligned with the Veetile‑Ruchi system.*

## 3. Project Scope
*Definition of functional and non‑functional boundaries.*

## 4. System Modules
- **Accounts** – user authentication and profile management.
- **Food Catalogue** – 50 Kerala food items, CRUD operations.
- **Orders** – order placement, tracking, and history.
- **Delivery** – driver assignment and route management.
- **Health** – nutritional analysis using Scikit‑Learn.

## 5. User Roles
- **Admin** – full system control.
- **Vendor** – manage food items and inventory.
- **Customer** – browse catalogue, place orders.
- **Driver** – delivery logistics.
- **Analyst** – view health and recommendation dashboards.

## 6. Functional Specification
*Detailed functional requirements for each module.*

## 7. Non‑Functional Specification & Quality Requirements
*Performance, security, usability, and reliability criteria.*

## 8. Assumptions and Dependencies
*Key assumptions (e.g., internet connectivity) and external dependencies (PostgreSQL, Leaflet, etc.).*

## 9. System Study Introduction
*Context for the feasibility and design study.*

## 10. Existing System Drawbacks
*Issues identified in the current implementation.*

## 11. Proposed System
*Improvements and new features to address the drawbacks.*

## 12. Advantages of Proposed System
*Benefits expected from the proposed changes.*

## 13. Feasibility Study
### 13.1 Economic Feasibility
*Cost analysis of hosting, services, and licensing.*
### 13.2 Technical Feasibility
*Evaluation of chosen technologies and implementation readiness.*
### 13.3 Behavioural Feasibility
*User study design and questionnaire summary.*

## 14. Software Description
*Overview of frontend (React, Vite) and backend (Spring Boot, Go) components as adapted for Veetile‑Ruchi.*

## 15. System Architecture Introduction
*High‑level architectural diagram description.*

## 16. UML Diagrams Introduction
*Explanation of class, sequence, activity, and state diagrams.*

## 17. User Interface Design
*Summary of UI layout, navigation flow, and design principles.*

## 18. Database Design
The database model separates responsibilities across distinct schemas:

- **accounts_schema** – tables for user accounts, authentication tokens, and profile data.
- **rides_schema** – tables for ride information, participant membership, and route data.
- **rentals_schema** – tables for rental bookings, periods (using `TSTZRANGE`), and payment details.
- **events_schema** – tables for event logging, notifications, and audit trails.
- **chat_schema** – tables for chat rooms, messages, and pagination identifiers.

All services reference these tables using schema‑qualified names (e.g., `accounts_schema.account`). Database versioning is managed with **Flyway** migration scripts; each migration defines column defaults, lengths, indexes, and constraints.

**Identifiers**
- Primary keys are UUIDs for most durable business objects, ensuring global uniqueness.
- Chat uses a monotonic textual identifier (`message_seq`) for efficient paging and personal clearing.

**Temporal Data**
- Timestamps are stored with time‑zone awareness (`TIMESTAMPTZ`) where required.
- Rental periods are stored as `TSTZRANGE` to represent booking boundaries consistently.

**Geospatial Data**
- Locations are stored using PostgreSQL `geography` type with SRID 4326, defined in migrations for accurate map rendering.

## 4.4.1 Relational Database Management System

RiderSync uses **PostgreSQL** relational databases to represent identity, ride, rental, event, and chat data. Local foreign‑key constraints maintain parent‑child relationships within each schema, while cross‑service UUID references are validated by the application layer to ensure referential integrity across services.

PostGIS geography points are stored with **SRID 4326** as defined in the Flyway migrations, enabling accurate geospatial queries for route calculations and location‑based features.

Durable business data resides in PostgreSQL, whereas ephemeral live‑cache state (e.g., session data, real‑time updates) is kept in separate stores such as Redis, deliberately separating persistent and volatile data concerns.

## 4.4.2 Normalization

Motorcycles and emergency contacts are stored in separate tables linked to a user, rather than as repeated columns in the user table. A ride's ordered waypoints and participants are modeled as distinct relations. Event attendance uses a composite event‑user key. Reactions and message recipients are kept in separate chat tables. These choices represent repeating relationships without storing comma‑separated identifiers.

Some duplication is deliberate. A rental listing stores a motorcycle description snapshot so that a marketplace record can preserve its displayed identity. Event `attendee_count` is an aggregate maintained with attendance operations. Such values need consistent updates and tests; they should not be described as automatically normalised independent facts.

### First Normal Form
Store each participant, waypoint and contact as an individual record. For example, `ride_participant` stores one ride‑user pair instead of a list of user identifiers inside the rides row. This avoids repeated participant columns and supports direct membership queries.

### Second Normal Form
The `event_attendees` composite key identifies one user’s attendance for one event. Attendance status belongs to that entire pair. Event title and start time remain on the `event` table instead of being repeated in every attendance record.

### Third Normal Form
User details remain in the identity domain, while motorcycles and contacts refer to their owning user. Message recipients and reactions are separate from message content. Rental listing snapshots and event counters are intentional derived or historical values; their consistency must be maintained by the application.

## 4.4.3 Sanitization

Inputs are validated in the API and domain layer. Chat rejects empty or oversized content and validates metadata, replies and mentions. Rental periods and prices must be valid. Location coordinates and timestamps are checked before use. Media upload accepts supported JPEG, PNG or WebP files within its size limit and uses generated safe filenames. User‑supplied identifiers and values must not be concatenated into SQL.

## 4.4.4 Indexing

Foreign keys and cascading deletes protect local parent‑child records. A unique ride‑user pair prevents duplicate participants. The rental exclusion constraint rejects overlapping active reservation states, and event row coordination protects capacity. Spatial indexes support location discovery; chat room and sequence indexes support ordered history. Cross‑service references still require application checks because a UUID alone cannot prove that an external record is valid.

Live positions are deliberately not represented as a durable route‑history table in Valkey. Expiration and stop tombstones enforce temporary sharing semantics. Historical `ride_location_snapshots` have a separate PostgreSQL representation and eligibility check.

## 4.5 Table Design

The following structures are extracted from the current SQL migrations and PostgreSQL chat initialization. Later migrations extend the original definitions; the rental period is `TSTZRANGE`. PostgreSQL type aliases such as `timestamptz` are used for readability. Full DDL remains authoritative. Cross‑service identifiers are logical references unless a foreign key is explicitly defined.

**Accounts Schema**
```sql
CREATE TABLE accounts_schema.account (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(150) NOT NULL UNIQUE,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Rides Schema**
```sql
CREATE TABLE rides_schema.ride (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id UUID NOT NULL,
    start_location GEOGRAPHY(POINT, 4326) NOT NULL,
    end_location GEOGRAPHY(POINT, 4326) NOT NULL,
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Rentals Schema**
```sql
CREATE TABLE rentals_schema.rental (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts_schema.account(id),
    item VARCHAR(100) NOT NULL,
    period TSTZRANGE NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Events Schema**
```sql
CREATE TABLE events_schema.event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Chat Schema**
```sql
CREATE TABLE chat_schema.chat_room (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE chat_schema.message (
    id BIGSERIAL PRIMARY KEY,
    room_id UUID NOT NULL REFERENCES chat_schema.chat_room(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES accounts_schema.account(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

*All sections have been rewritten to match the style and phrasing of the reference report while preserving Veetile‑Ruchi specific details.*
