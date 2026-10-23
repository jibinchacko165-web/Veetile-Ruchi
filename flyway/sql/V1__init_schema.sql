-- Flyway migration V1__init_schema.sql
-- This migration creates core schemas and tables for Veetile‑Ruchi.

-- Create schemas
CREATE SCHEMA IF NOT EXISTS accounts_schema;
CREATE SCHEMA IF NOT EXISTS rides_schema;
CREATE SCHEMA IF NOT EXISTS rentals_schema;
CREATE SCHEMA IF NOT EXISTS events_schema;
CREATE SCHEMA IF NOT EXISTS chat_schema;

-- accounts_schema tables
CREATE TABLE accounts_schema.account (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(150) NOT NULL UNIQUE,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE accounts_schema.profile (
    account_id UUID PRIMARY KEY REFERENCES accounts_schema.account(id) ON DELETE CASCADE,
    full_name VARCHAR(200),
    phone_number VARCHAR(20),
    avatar_url TEXT,
    bio TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- rides_schema tables
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

CREATE TABLE rides_schema.ride_participant (
    ride_id UUID NOT NULL REFERENCES rides_schema.ride(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts_schema.account(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ride_id, account_id)
);

-- rentals_schema tables
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

-- events_schema tables
CREATE TABLE events_schema.event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- chat_schema tables
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

-- Indexes for performance
CREATE INDEX idx_account_email ON accounts_schema.account(email);
CREATE INDEX idx_ride_start ON rides_schema.ride(start_location);
CREATE INDEX idx_ride_end ON rides_schema.ride(end_location);
CREATE INDEX idx_rental_period ON rentals_schema.rental USING GIST (period);
CREATE INDEX idx_event_type ON events_schema.event(event_type);
CREATE INDEX idx_message_room ON chat_schema.message(room_id);

-- Additional schemas for Veetile‑Ruchi business entities

CREATE SCHEMA IF NOT EXISTS food_schema;
CREATE SCHEMA IF NOT EXISTS health_schema;
CREATE SCHEMA IF NOT EXISTS cart_schema;
CREATE SCHEMA IF NOT EXISTS orders_schema;
CREATE SCHEMA IF NOT EXISTS inventory_schema;
CREATE SCHEMA IF NOT EXISTS delivery_schema;
CREATE SCHEMA IF NOT EXISTS gps_schema;
CREATE SCHEMA IF NOT EXISTS feedback_schema;

-- food_schema tables
CREATE TABLE food_schema.food_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    price NUMERIC(10,2) NOT NULL,
    nutrition JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- health_schema tables
CREATE TABLE health_schema.health_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts_schema.account(id),
    preferences JSONB,
    allergies TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- cart_schema tables
CREATE TABLE cart_schema.cart (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts_schema.account(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE cart_schema.cart_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id UUID NOT NULL REFERENCES cart_schema.cart(id) ON DELETE CASCADE,
    food_id UUID NOT NULL REFERENCES food_schema.food_item(id),
    quantity INT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- orders_schema tables
CREATE TABLE orders_schema.order (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(20) NOT NULL UNIQUE,
    account_id UUID NOT NULL REFERENCES accounts_schema.account(id),
    status VARCHAR(20) NOT NULL,
    total NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE orders_schema.order_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders_schema.order(id) ON DELETE CASCADE,
    food_id UUID NOT NULL REFERENCES food_schema.food_item(id),
    quantity INT NOT NULL,
    price NUMERIC(10,2) NOT NULL
);

-- inventory_schema tables
CREATE TABLE inventory_schema.inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    food_id UUID NOT NULL REFERENCES food_schema.food_item(id),
    quantity INT NOT NULL,
    location GEOGRAPHY(POINT, 4326)
);

-- delivery_schema tables
CREATE TABLE delivery_schema.delivery_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders_schema.order(id),
    courier_id UUID NOT NULL REFERENCES accounts_schema.account(id),
    status VARCHAR(20) NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- gps_schema tables
CREATE TABLE gps_schema.courier_location (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    courier_id UUID NOT NULL REFERENCES accounts_schema.account(id),
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- feedback_schema tables
CREATE TABLE feedback_schema.feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders_schema.order(id),
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for new tables
CREATE INDEX idx_food_name ON food_schema.food_item(name);
CREATE INDEX idx_order_number ON orders_schema.order(order_number);
CREATE INDEX idx_delivery_status ON delivery_schema.delivery_assignment(status);
