CREATE TABLE `plan_node_subscriptions` (
  `node_address` varchar(100) NOT NULL,
  `uuid` varchar(255) NOT NULL,
  `plan_id` mediumint DEFAULT NULL,
  `plan_subscription_id` mediumint DEFAULT NULL,
  `node_subscription_id` mediumint DEFAULT NULL,
  `deposit` varchar(100) DEFAULT NULL,
  `hours` mediumint DEFAULT NULL,
  `inactive_date` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`node_address`,`uuid`)