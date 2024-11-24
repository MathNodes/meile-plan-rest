CREATE TABLE `meile_plans` (
  `uuid` varchar(100) NOT NULL,
  `subscription_id` bigint unsigned DEFAULT NULL,
  `plan_id` bigint unsigned DEFAULT NULL,
  `plan_name` varchar(256) DEFAULT NULL,
  `plan_price` bigint unsigned DEFAULT NULL,
  `plan_denom` varchar(100) DEFAULT NULL,
  `expiration_date` timestamp NULL DEFAULT NULL,
  `logo` varchar(1000) DEFAULT NULL,
  PRIMARY KEY (`uuid`)