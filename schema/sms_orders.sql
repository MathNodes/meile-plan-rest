-- Meile SMS: the SMS numbers (orders) purchased by a UUID.
--
-- One row is created per successful purchase. It records what was bought and
-- how much the user was charged (SMSPool cost + Meile markup) so an order can
-- be shown, timed out, and refunded on cancellation.
--
-- Database: sms
-- Table:    orders

CREATE TABLE `orders` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `uuid` varchar(100) NOT NULL,
  `provider_order_id` varchar(100) DEFAULT NULL,
  `country_id` int DEFAULT NULL,
  `country` varchar(100) DEFAULT NULL,
  `service_id` int DEFAULT NULL,
  `service` varchar(100) DEFAULT NULL,
  `phone_number` varchar(50) DEFAULT NULL,
  `cost` decimal(20,6) DEFAULT NULL,
  `markup` decimal(8,4) DEFAULT NULL,
  `total_charged` decimal(20,6) DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'active',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expires_at` timestamp NULL DEFAULT NULL,
  `cancelled_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `uuid` (`uuid`),
  KEY `provider_order_id` (`provider_order_id`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
