-- Meile SMS: audit trail of every movement of a user's SMS balance.
--
-- A row is written every time a balance changes:
--   * type = 'topup'    -> the user added funds with a coin (e.g. pirate/arrr)
--   * type = 'purchase' -> the user bought an SMS number (amount is negative)
--   * type = 'refund'   -> a cancelled number was credited back
--
-- `amount` is signed (positive = credit, negative = debit) while
-- `balance_after` stores the resulting balance so a statement can be rebuilt.
--
-- Database: sms
-- Table:    transactions

CREATE TABLE `transactions` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `uuid` varchar(100) NOT NULL,
  `type` varchar(20) NOT NULL,
  `amount` decimal(20,6) NOT NULL,
  `balance_after` decimal(20,6) NOT NULL,
  `denom` varchar(10) NOT NULL DEFAULT 'USD',
  `coin` varchar(20) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `txid` varchar(255) DEFAULT NULL,
  `reference` varchar(100) DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'complete',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `uuid` (`uuid`),
  KEY `type` (`type`),
  KEY `reference` (`reference`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
