-- Meile SMS: per-app (anonymous UUID) balance ledger
--
-- The GUI identifies a user by the UUID stored in their local config
-- (see PreLoadWindow.GenerateUUID in meile-gui/src/ui/screens.py). Since the
-- UUID is unique and contains no personal information, it is a good anonymous
-- key for tracking SMS credit.
--
-- Database: sms
-- Table:    balances

CREATE TABLE `balances` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `uuid` varchar(100) NOT NULL,
  `balance` decimal(20,6) NOT NULL DEFAULT '0.000000',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
