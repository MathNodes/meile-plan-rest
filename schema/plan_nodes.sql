CREATE TABLE `plan_nodes` (
  `uuid` varchar(100) NOT NULL,
  `node_address` varchar(255) NOT NULL,
  PRIMARY KEY (`uuid`,`node_address`)