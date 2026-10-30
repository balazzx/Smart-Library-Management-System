-- Smart Library Management System Database Schema
-- Compatible with MySQL 8.0+

CREATE DATABASE IF NOT EXISTS `smart_library_db` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `smart_library_db`;

-- Users & Authentication
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(80) UNIQUE NOT NULL,
    `email` VARCHAR(120) UNIQUE NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('STUDENT', 'LIBRARIAN', 'ADMIN') NOT NULL DEFAULT 'STUDENT',
    `is_active` BOOLEAN DEFAULT TRUE,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Departments
CREATE TABLE IF NOT EXISTS `departments` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `code` VARCHAR(20) UNIQUE NOT NULL,
    `name` VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Students
CREATE TABLE IF NOT EXISTS `students` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT UNIQUE NOT NULL,
    `student_id` VARCHAR(50) UNIQUE NOT NULL,
    `name` VARCHAR(120) NOT NULL,
    `department_id` INT NOT NULL,
    `phone` VARCHAR(20),
    `library_card_number` VARCHAR(50) UNIQUE NOT NULL,
    `max_borrow_limit` INT DEFAULT 5,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`department_id`) REFERENCES `departments`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Librarians
CREATE TABLE IF NOT EXISTS `librarians` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT UNIQUE NOT NULL,
    `staff_id` VARCHAR(50) UNIQUE NOT NULL,
    `name` VARCHAR(120) NOT NULL,
    `department_id` INT,
    `phone` VARCHAR(20),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`department_id`) REFERENCES `departments`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Authors, Categories, Publishers
CREATE TABLE IF NOT EXISTS `authors` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(150) NOT NULL,
    `bio` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `categories` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) UNIQUE NOT NULL,
    `description` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `publishers` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(150) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Smart Shelf Locations
CREATE TABLE IF NOT EXISTS `book_locations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `block` VARCHAR(50) NOT NULL,
    `floor` VARCHAR(20) NOT NULL,
    `section` VARCHAR(50) NOT NULL,
    `rack` VARCHAR(20) NOT NULL,
    `shelf` VARCHAR(20) NOT NULL,
    `position` VARCHAR(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Books
CREATE TABLE IF NOT EXISTS `books` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `isbn` VARCHAR(20) UNIQUE NOT NULL,
    `author_id` INT NOT NULL,
    `category_id` INT NOT NULL,
    `publisher_id` INT NOT NULL,
    `pub_year` INT NOT NULL,
    `language` VARCHAR(50) DEFAULT 'English',
    `description` TEXT,
    `cover_image` VARCHAR(255) DEFAULT 'default_cover.jpg',
    `location_id` INT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`author_id`) REFERENCES `authors`(`id`),
    FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`),
    FOREIGN KEY (`publisher_id`) REFERENCES `publishers`(`id`),
    FOREIGN KEY (`location_id`) REFERENCES `book_locations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Physical Book Copies
CREATE TABLE IF NOT EXISTS `book_copies` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `copy_code` VARCHAR(50) UNIQUE NOT NULL,
    `book_id` INT NOT NULL,
    `acquisition_date` DATE DEFAULT (CURRENT_DATE),
    `condition_status` ENUM('EXCELLENT', 'GOOD', 'FAIR', 'DAMAGED') DEFAULT 'EXCELLENT',
    `status` ENUM('AVAILABLE', 'ISSUED', 'RESERVED', 'LOST', 'DAMAGED', 'ARCHIVED') DEFAULT 'AVAILABLE',
    `location_id` INT,
    FOREIGN KEY (`book_id`) REFERENCES `books`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`location_id`) REFERENCES `book_locations`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Transactions & Requests
CREATE TABLE IF NOT EXISTS `book_requests` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `book_id` INT NOT NULL,
    `request_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `status` ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'FULFILLED') DEFAULT 'PENDING',
    `reviewer_id` INT,
    `review_date` DATETIME,
    `notes` TEXT,
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`),
    FOREIGN KEY (`book_id`) REFERENCES `books`(`id`),
    FOREIGN KEY (`reviewer_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `borrow_transactions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `copy_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `issue_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `due_date` DATETIME NOT NULL,
    `return_date` DATETIME,
    `status` ENUM('ISSUED', 'RETURNED', 'OVERDUE', 'LOST') DEFAULT 'ISSUED',
    `fine_amount` DECIMAL(10,2) DEFAULT 0.00,
    `is_fine_paid` BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (`copy_id`) REFERENCES `book_copies`(`id`),
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `return_transactions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `borrow_transaction_id` INT NOT NULL,
    `return_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `condition_on_return` VARCHAR(50) DEFAULT 'GOOD',
    `fine_assessed` DECIMAL(10,2) DEFAULT 0.00,
    `notes` TEXT,
    FOREIGN KEY (`borrow_transaction_id`) REFERENCES `borrow_transactions`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Reservations & Waiting Lists
CREATE TABLE IF NOT EXISTS `reservations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `book_id` INT NOT NULL,
    `reservation_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `status` ENUM('PENDING', 'FULFILLED', 'EXPIRED', 'CANCELLED') DEFAULT 'PENDING',
    `queue_position` INT DEFAULT 1,
    `expiry_date` DATETIME,
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`),
    FOREIGN KEY (`book_id`) REFERENCES `books`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `waiting_list` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `book_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `joined_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `queue_position` INT NOT NULL,
    `status` ENUM('WAITING', 'NOTIFIED', 'EXPIRED', 'FULFILLED') DEFAULT 'WAITING',
    `notified_at` DATETIME,
    FOREIGN KEY (`book_id`) REFERENCES `books`(`id`),
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Wishlists, Ratings & Reviews
CREATE TABLE IF NOT EXISTS `wishlist` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `book_id` INT NOT NULL,
    `added_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_wishlist` (`student_id`, `book_id`),
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`),
    FOREIGN KEY (`book_id`) REFERENCES `books`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `ratings_reviews` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `book_id` INT NOT NULL,
    `rating` INT NOT NULL CHECK (`rating` BETWEEN 1 AND 5),
    `review_text` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_review` (`student_id`, `book_id`),
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`),
    FOREIGN KEY (`book_id`) REFERENCES `books`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Fines & Digital Resources
CREATE TABLE IF NOT EXISTS `fines` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `transaction_id` INT,
    `amount` DECIMAL(10,2) NOT NULL,
    `reason` VARCHAR(255) NOT NULL,
    `status` ENUM('UNPAID', 'PAID', 'WAIVED') DEFAULT 'UNPAID',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `paid_at` DATETIME,
    `payment_method` VARCHAR(50),
    `transaction_ref` VARCHAR(100),
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`),
    FOREIGN KEY (`transaction_id`) REFERENCES `borrow_transactions`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `digital_resources` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `author` VARCHAR(150),
    `description` TEXT,
    `category_id` INT,
    `file_path` VARCHAR(255) NOT NULL,
    `file_type` VARCHAR(20) NOT NULL,
    `file_size` INT NOT NULL,
    `target_department_id` INT,
    `upload_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `uploaded_by` INT,
    FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`),
    FOREIGN KEY (`target_department_id`) REFERENCES `departments`(`id`),
    FOREIGN KEY (`uploaded_by`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Communications & System Logs
CREATE TABLE IF NOT EXISTS `announcements` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(200) NOT NULL,
    `message` TEXT NOT NULL,
    `priority` ENUM('LOW', 'MEDIUM', 'HIGH', 'URGENT') DEFAULT 'MEDIUM',
    `target_department_id` INT,
    `target_role` VARCHAR(20) DEFAULT 'ALL',
    `start_date` DATE NOT NULL,
    `end_date` DATE NOT NULL,
    `created_by` INT NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`target_department_id`) REFERENCES `departments`(`id`),
    FOREIGN KEY (`created_by`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `title` VARCHAR(150) NOT NULL,
    `message` TEXT NOT NULL,
    `category` VARCHAR(50) DEFAULT 'System',
    `is_read` BOOLEAN DEFAULT FALSE,
    `link` VARCHAR(255),
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `email_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `recipient` VARCHAR(120) NOT NULL,
    `subject` VARCHAR(200) NOT NULL,
    `email_type` VARCHAR(50) NOT NULL,
    `sent_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `status` ENUM('SENT', 'FAILED', 'PENDING') DEFAULT 'PENDING',
    `error_message` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `audit_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT,
    `role` VARCHAR(20),
    `action` VARCHAR(100) NOT NULL,
    `entity` VARCHAR(50),
    `entity_id` INT,
    `description` TEXT,
    `ip_address` VARCHAR(45),
    `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `search_history` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `query_text` VARCHAR(255) NOT NULL,
    `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `system_settings` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `setting_key` VARCHAR(100) UNIQUE NOT NULL,
    `setting_value` TEXT NOT NULL,
    `description` VARCHAR(255),
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
