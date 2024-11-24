CREATE TABLE `meile_subscriptions` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `uuid` varchar(100) DEFAULT NULL,
  `wallet` varchar(100) DEFAULT NULL,
  `subscription_id` bigint unsigned DEFAULT NULL,
  `plan_id` bigint unsigned DEFAULT NULL,
  `amt_paid` decimal(24,12) DEFAULT NULL,
  `amt_denom` varchar(10) DEFAULT NULL,
  `subscribe_date` timestamp NULL DEFAULT NULL,
  `subscription_duration` smallint unsigned DEFAULT NULL,
  `expires` timestamp NULL DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`)