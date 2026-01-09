-- SQL script to create user chris123 with permissions to edit auto_tickets_itsr_network table
-- Database: auto_tickets
-- Table: auto_tickets_itsr_network
-- Run this script as root user: mysql -h 172.19.11.14 -u root -p < create_chris123_user.sql

-- Drop user if exists (to recreate with new permissions)
DROP USER IF EXISTS 'chris123'@'%';

-- Create the user
CREATE USER 'chris123'@'%' IDENTIFIED BY 'chris123';

-- Grant permissions to edit (INSERT, UPDATE, DELETE) and SELECT on the specific table
-- Only permissions on auto_tickets_itsr_network table
GRANT SELECT, INSERT, UPDATE, DELETE ON auto_tickets.auto_tickets_itsr_network TO 'chris123'@'%';

-- Flush privileges to apply changes
FLUSH PRIVILEGES;

-- Verify the grants
SHOW GRANTS FOR 'chris123'@'%';
