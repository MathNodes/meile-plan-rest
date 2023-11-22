--- Create Meile Plan Table

CREATE TABLE meile_plans (uuid VARCHAR(100), subscription_id BIGINT UNSIGNED, plan_id BIGINT UNSIGNED, plan_name VARCHAR(256), plan_price BIGINT UNSIGNED, plan_denom VARCHAR(100), expiration_date TIMESTAMP PRIMARY KEY(uuid));

--- Create Meile Subscriber Table
CREATE TABLE meile_subscriptions (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, uuid VARCHAR(100), wallet VARCHAR(100), subscription_id BIGINT UNSIGNED, plan_id BIGINT UNSIGNED,  amt_paid DECIMAL(24,12), amt_denom VARCHAR(10), subscribe_date TIMESTAMP, subscription_duration SMALLINT UNSIGNED, expires TIMESTAMP, PRIMARY KEY(id));

--- Create Plan Nodes Table
CREATE TABLE plan_nodes (uuid VARCHAR(100), node_address VARCHAR(255), PRIMARY KEY(uuid, node_address));