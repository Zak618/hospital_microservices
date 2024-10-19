CREATE DATABASE hospitals_db;
CREATE DATABASE timetable_db;
CREATE DATABASE documents_db;

\c accounts_db;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password TEXT NOT NULL,
    roles VARCHAR(100) NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE
);
